"""
Export depth, RGB, IR and point clouds from an Azure Kinect DK MKV file.
导出 Azure Kinect 回放中的深度、彩色、红外与点云数据。

  python export_pyk4a.py -n wet_pyk4a
  python export_pyk4a.py -i /path/to/clip.mkv -o /path/to/out

English:
Reads video/<name>.mkv (color recorded as MJPG or BGRA32) and exports every capture
that has both depth and color to output/<name>/pyk4a/:
- color/: raw color images (.png)
- depth/: raw depth in the depth camera frame (uint16 .npy, mm)
- depth_vis/: pseudo-color depth visualizations (.png)
- color_aligned/: color reprojected into the depth camera frame (.png)
- ir/: IR frames (uint16 .npy)
- point_cloud/: depth point clouds (HxWx3 .npy, mm)
- intrinsic_{color,depth}.txt, distortion_{color,depth}.txt

中文：
读取 video/<name>.mkv（彩色为 MJPG 或 BGRA32 均可），对同时含深度和彩色的 capture 导出到 output/<name>/pyk4a/：
- color/: 原始彩色图像（.png）
- depth/: 深度相机坐标系下的原始深度（uint16 .npy，毫米）
- depth_vis/: 伪彩可视化深度图（.png）
- color_aligned/: 对齐到深度相机的彩色图像（.png）
- ir/: 红外图（uint16 .npy）
- point_cloud/: 深度点云（HxWx3 .npy，毫米）
- intrinsic_{color,depth}.txt、distortion_{color,depth}.txt
"""
import argparse
import itertools
import os
import sys
import cv2
import numpy as np
from pyk4a import PyK4APlayback
from pyk4a.calibration import CalibrationType
from pyk4a.transformation import color_image_to_depth_camera

def depth_to_colormap(depth: np.ndarray) -> np.ndarray:
    """Convert uint16 depth to a visible pseudo-color image."""
    valid = depth > 0  # 
    if not np.any(valid):
        return np.zeros((depth.shape[0], depth.shape[1], 3), dtype=np.uint8)

    values = depth[valid].astype(np.float32)
    lo = np.percentile(values, 2)
    hi = np.percentile(values, 98)
    if hi <= lo:
        hi = lo + 1.0


    scaled = ((depth.astype(np.float32) - lo) * 255.0 / (hi - lo)).clip(0, 255)
    scaled[~valid] = 0
    scaled_u8 = scaled.astype(np.uint8)
    return cv2.applyColorMap(scaled_u8, cv2.COLORMAP_TURBO)

def normalize_color_frame(color_raw: np.ndarray) -> np.ndarray | None:
    """Normalize color payload into a standard HxWx3 BGR image."""
    if color_raw is None:
        return None

    # Common in MKV playback: encoded color bytes stored as (N, 1) or (1, N).
    if isinstance(color_raw, np.ndarray) and color_raw.dtype == np.uint8 and (
        color_raw.ndim == 1
        or (color_raw.ndim == 2 and (color_raw.shape[0] == 1 or color_raw.shape[1] == 1))
    ):
        encoded = color_raw.reshape(-1)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if decoded is not None:
            return decoded

    if isinstance(color_raw, np.ndarray) and color_raw.ndim == 3 and color_raw.shape[2] == 4:
        return cv2.cvtColor(color_raw, cv2.COLOR_BGRA2BGR)

    if isinstance(color_raw, np.ndarray) and color_raw.ndim == 3 and color_raw.shape[2] == 3:
        return color_raw

    if isinstance(color_raw, np.ndarray) and color_raw.ndim == 2:
        # If this is already a single-channel image, keep it savable as 3-channel BGR.
        return cv2.cvtColor(color_raw, cv2.COLOR_GRAY2BGR)

    return None


def save_intrinsics(playback, output_dir: str):
    """Save camera intrinsics to the specified output directory.""" 
    
    K_depth = playback.calibration.get_camera_matrix(CalibrationType.DEPTH)
    K_RGB = playback.calibration.get_camera_matrix(CalibrationType.COLOR)
    
    np.savetxt(os.path.join(output_dir, "intrinsic_depth.txt"), K_depth, fmt="%.9f")
    np.savetxt(os.path.join(output_dir, "intrinsic_color.txt"), K_RGB, fmt="%.9f")
    
    dist_depth = playback.calibration.get_distortion_coefficients(CalibrationType.DEPTH)
    np.savetxt(os.path.join(output_dir, "distortion_depth.txt"), dist_depth, fmt="%.9f")
    dist_color = playback.calibration.get_distortion_coefficients(CalibrationType.COLOR)
    np.savetxt(os.path.join(output_dir, "distortion_color.txt"), dist_color, fmt="%.9f")


def align_color_to_depth(color_bgr: np.ndarray, depth: np.ndarray, playback) -> np.ndarray:
    """Reproject color into the depth camera frame.

    capture.transformed_color only works for BGRA32 recordings, so decode first and
    call the SDK transformation on the BGRA image ourselves (works for MJPG too).
    """
    color_bgra = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2BGRA)
    aligned = color_image_to_depth_camera(color_bgra, depth, playback.calibration, playback.thread_safe)
    return cv2.cvtColor(aligned, cv2.COLOR_BGRA2BGR)


class SimpleProgressBar:
    def __init__(self, total: int | None = None):
        self.total = total
        self.current = 0
        self.spinner = itertools.cycle(["|", "/", "-", "\\"])

    def update(self, increment: int = 1) -> None:
        self.current += increment
        if self.total is not None:
            percent = min(100, int(self.current / self.total * 100)) if self.total else 0
            filled = int(percent / 2)
            bar = f"[{'#' * filled}{'-' * (50 - filled)}] {percent:3d}%"
            sys.stdout.write(f"\r{bar} ({self.current}/{self.total})")
        else:
            sys.stdout.write(f"\r{'Processing':<12} {next(self.spinner)} frame {self.current}")
        sys.stdout.flush()

    def close(self) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Export depth, color, IR and point clouds from an Azure Kinect MKV.")
    parser.add_argument("-n", "--name", default="wet_pyk4a",
                        help="scene name; reads video/<name>.mkv, writes output/<name>/pyk4a/")
    parser.add_argument("-i", "--input", default=None, help="MKV path (overrides --name)")
    parser.add_argument("-o", "--output", default=None, help="output directory (overrides the default)")
    args = parser.parse_args()

    mkv_path = args.input or os.path.join("video", f"{args.name}.mkv")
    output_dir = args.output or os.path.join("output", args.name, "pyk4a")
    if not os.path.exists(mkv_path):
        print(f"MKV not found: {mkv_path}")
        sys.exit(1)

    out = {sub: os.path.join(output_dir, sub)
           for sub in ("color", "depth", "depth_vis", "color_aligned", "ir", "point_cloud")}
    for d in out.values():
        os.makedirs(d, exist_ok=True)

    playback = PyK4APlayback(mkv_path)
    playback.open()
    save_intrinsics(playback, output_dir)
    frame_idx = 0
    saved_idx = 0
    skipped = 0
    progress = SimpleProgressBar()

    try:
        while True:
            try:
                capture = playback.get_next_capture()
            except EOFError:
                print("Reached end of MKV file.")
                break

            frame_idx += 1
            depth_raw = capture.depth
            color_img = normalize_color_frame(capture.color)
            # 未开启同步录制时，开头几帧可能只有深度或只有彩色，直接跳过
            if depth_raw is None or color_img is None:
                skipped += 1
                continue

            # 保存原始数据
            stem = f"{saved_idx:06d}"
            np.save(os.path.join(out["depth"], f"{stem}.npy"), depth_raw)
            if capture.ir is not None:
                np.save(os.path.join(out["ir"], f"{stem}.npy"), capture.ir)
            cv2.imwrite(os.path.join(out["color"], f"{stem}.png"), color_img)

            # 生成&保存可视化的深度数据
            cv2.imwrite(os.path.join(out["depth_vis"], f"{stem}.png"), depth_to_colormap(depth_raw))

            # 生成&保存对齐到深度相机的彩色图像
            cv2.imwrite(os.path.join(out["color_aligned"], f"{stem}.png"),
                        align_color_to_depth(color_img, depth_raw, playback))

            # 生成&保存深度镜头的点云数据
            np.save(os.path.join(out["point_cloud"], f"{stem}.npy"), capture.depth_point_cloud)

            saved_idx += 1
            progress.update()
    finally:
        playback.close()
        progress.close()

    print(f"Processed {frame_idx} captures, saved {saved_idx}, skipped {skipped} incomplete → {output_dir}")

if __name__ == "__main__":
    main()
