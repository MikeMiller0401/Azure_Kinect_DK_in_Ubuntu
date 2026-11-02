import open3d as o3d
import numpy as np
import cv2
import os
from tqdm import tqdm
from pyk4a import PyK4APlayback
from pyk4a.calibration import CalibrationType

# 深度伪彩图的固定可视化范围（毫米），超出范围的像素会被截断成同一颜色，按拍摄场景调整
DEPTH_VIS_MIN_MM = 0
DEPTH_VIS_MAX_MM = 550


def save_color(capture, color_path, idx):
    color = np.asarray(capture.color)
    color = cv2.cvtColor(color, cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(color_path, f"{idx:06d}.png"), color)


def save_depth(capture, depth_path, idx):
    # Open3D 读出的深度已对齐到彩色相机（与彩色图同分辨率），对应的内参是 K_rgb
    depth = np.asarray(capture.depth)
    # 1. 先保存原始深度数据（这个数据本身是稳定的，单位是毫米 mm）
    np.save(os.path.join(depth_path, f"{idx:06d}.npy"), depth)

    # 2. 使用固定的可视化范围，保证不同帧之间颜色可比
    min_distance = DEPTH_VIS_MIN_MM
    max_distance = DEPTH_VIS_MAX_MM

    # 3. 裁剪数据并将其固定映射到 0-255
    # 将超出范围的值截断
    depth_clipped = np.clip(depth, min_distance, max_distance)
    # 线性映射到 0-255: (val - min) / (max - min) * 255
    depth_vis = ((depth_clipped - min_distance) / (max_distance - min_distance) * 255).astype(np.uint8)

    # 4. 如果你想让无效像素（0mm）显示为黑色，可以加这一步：
    depth_vis[depth == 0] = 0 

    # 5. 生成伪彩色并保存
    depth_heatmap = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
    cv2.imwrite(os.path.join(depth_path, f"{idx:06d}.png"), depth_heatmap)

def save_camera(video_path, save_path):
    playback = PyK4APlayback(video_path)
    playback.open()

    K_rgb = playback.calibration.get_camera_matrix(CalibrationType.COLOR)
    K_depth = playback.calibration.get_camera_matrix(CalibrationType.DEPTH)
    
    np.savetxt(os.path.join(save_path, "K_rgb.txt"), K_rgb, fmt="%.8f")
    np.savetxt(os.path.join(save_path, "K_depth.txt"), K_depth, fmt="%.8f")

    playback.close()

    print("Saved K_rgb.txt and K_depth.txt")


if __name__ == "__main__":
    # config = o3d.io.read_azure_kinect_mkv_metadata("/home/tcy/PycharmProjects/AzureKinectDK_Ubuntu26/video/test003.mkv")
    # print(config["device_metadata"]["serial_number"])

    reader = o3d.io.AzureKinectMKVReader()
    # metadate = reader.get_metadata()
    video_name = "wet_open3d"
    video_path = os.path.join("video", video_name + ".mkv")
    output_path = os.path.join("output", video_name)
    success = reader.open(video_path)
    print("open:", success)

    if not success:
        raise RuntimeError("Failed to open mkv file")

    color_path = os.path.join(output_path, "color")
    depth_path = os.path.join(output_path,"depth")
    os.makedirs(color_path, exist_ok=True)
    os.makedirs(depth_path, exist_ok=True)

    pbar = tqdm(desc="Decoding MKV frames", unit="frame")

    i = 0
    while not reader.is_eof():
        rgbd = reader.next_frame()
        if rgbd is None:
            continue

        save_color(rgbd, color_path, i)
        save_depth(rgbd, depth_path, i)

        i += 1
        pbar.update(1)   # ✅ 更新进度条

    pbar.close()
    reader.close()
    if i == 0:
        raise RuntimeError("No frames decoded. Open3D can only read MJPG recordings, not BGRA32.")
    save_camera(video_path, output_path)
    print("Done:", i, "frames")