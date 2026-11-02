"""
Export color and color-aligned depth from an Azure Kinect MKV with Open3D.
使用 Open3D 导出彩色图和对齐到彩色相机的深度。

  python export_open3d.py -n wet_open3d
  python export_open3d.py -n wet_open3d --vis-max 1500

Writes output/<name>/open3d/:
- color/: color images (.png)
- depth_aligned/: depth reprojected into the color camera (uint16 .npy, mm) — pair with intrinsic_color.txt
- depth_aligned_vis/: pseudo-color depth with a fixed range (.png)
- intrinsic_{color,depth}.txt, distortion_{color,depth}.txt

Open3D can only read MJPG recordings, not BGRA32.
"""
import argparse
import open3d as o3d
import numpy as np
import cv2
import os
from tqdm import tqdm
from pyk4a import PyK4APlayback

from export_pyk4a import save_intrinsics

# 深度伪彩图的默认固定可视化范围（毫米），超出范围的像素会被截断成同一颜色，按拍摄场景调整
DEPTH_VIS_MIN_MM = 0
DEPTH_VIS_MAX_MM = 550


def save_color(capture, color_path, idx):
    color = np.asarray(capture.color)
    color = cv2.cvtColor(color, cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(color_path, f"{idx:06d}.png"), color)


def save_depth(capture, depth_path, vis_path, idx, min_distance, max_distance):
    # Open3D 读出的深度已对齐到彩色相机（与彩色图同分辨率），对应的内参是 intrinsic_color.txt
    depth = np.asarray(capture.depth)
    # 1. 先保存原始深度数据（这个数据本身是稳定的，单位是毫米 mm）
    np.save(os.path.join(depth_path, f"{idx:06d}.npy"), depth)

    # 2. 使用固定的可视化范围，保证不同帧之间颜色可比
    # 3. 裁剪数据并将其固定映射到 0-255
    # 将超出范围的值截断
    depth_clipped = np.clip(depth, min_distance, max_distance)
    # 线性映射到 0-255: (val - min) / (max - min) * 255
    depth_vis = ((depth_clipped - min_distance) / (max_distance - min_distance) * 255).astype(np.uint8)

    # 4. 如果你想让无效像素（0mm）显示为黑色，可以加这一步：
    depth_vis[depth == 0] = 0

    # 5. 生成伪彩色并保存
    depth_heatmap = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
    cv2.imwrite(os.path.join(vis_path, f"{idx:06d}.png"), depth_heatmap)


def save_camera(video_path, save_path):
    playback = PyK4APlayback(video_path)
    playback.open()
    save_intrinsics(playback, save_path)
    playback.close()
    print("Saved intrinsic_{color,depth}.txt and distortion_{color,depth}.txt")


def main():
    parser = argparse.ArgumentParser(description="Export color and color-aligned depth from an Azure Kinect MKV with Open3D.")
    parser.add_argument("-n", "--name", default="wet_open3d",
                        help="scene name; reads video/<name>.mkv, writes output/<name>/open3d/")
    parser.add_argument("-i", "--input", default=None, help="MKV path (overrides --name)")
    parser.add_argument("-o", "--output", default=None, help="output directory (overrides the default)")
    parser.add_argument("--vis-min", type=float, default=DEPTH_VIS_MIN_MM, help="depth colormap lower bound in mm")
    parser.add_argument("--vis-max", type=float, default=DEPTH_VIS_MAX_MM, help="depth colormap upper bound in mm")
    args = parser.parse_args()
    if args.vis_max <= args.vis_min:
        parser.error("--vis-max must be greater than --vis-min")

    video_path = args.input or os.path.join("video", args.name + ".mkv")
    output_path = args.output or os.path.join("output", args.name, "open3d")

    reader = o3d.io.AzureKinectMKVReader()
    success = reader.open(video_path)
    print("open:", success)

    if not success:
        raise RuntimeError(f"Failed to open {video_path}")

    color_path = os.path.join(output_path, "color")
    depth_path = os.path.join(output_path, "depth_aligned")
    vis_path = os.path.join(output_path, "depth_aligned_vis")
    for d in (color_path, depth_path, vis_path):
        os.makedirs(d, exist_ok=True)

    pbar = tqdm(desc="Decoding MKV frames", unit="frame")

    i = 0
    while not reader.is_eof():
        rgbd = reader.next_frame()
        if rgbd is None:
            continue

        save_color(rgbd, color_path, i)
        save_depth(rgbd, depth_path, vis_path, i, args.vis_min, args.vis_max)

        i += 1
        pbar.update(1)

    pbar.close()
    reader.close()
    if i == 0:
        raise RuntimeError("No frames decoded. Open3D can only read MJPG recordings, not BGRA32.")
    save_camera(video_path, output_path)
    print(f"Done: {i} frames → {output_path}")


if __name__ == "__main__":
    main()
