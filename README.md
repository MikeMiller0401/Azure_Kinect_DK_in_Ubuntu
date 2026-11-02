# Azure Kinect DK Ubuntu Tools

中文：这是一个面向 Azure Kinect DK 的 Ubuntu 开发工具仓库，覆盖设备安装、视频录制、MKV 导出、相机内参保存、IMU 数据导出，以及基于深度和 IMU 的简单后处理脚本。

English: This repository contains Ubuntu-based tools for Azure Kinect DK, including device setup, video recording, MKV export, camera intrinsic export, IMU export, and lightweight post-processing utilities for depth and IMU data.

## 1. 项目内容 / What This Repository Provides

中文：仓库主要分成两条工作流，两者录制的 MKV（MJPG 彩色）可以互相导出。

- 基于 pyk4a 的录制与导出流程，适合直接在 Python 中访问彩色、深度、IR、点云和 IMU 数据。
- 基于 Open3D 的录制与导出流程，适合使用 Open3D 自带的 Azure Kinect MKV 读写接口。
- 若干辅助脚本，用于导出相机参数、统计深度图数据、以及从 IMU CSV 估计简单轨迹。

English: The repository is organized around two workflows. MKV files recorded by either one (MJPG color) can be exported by both.

- A pyk4a-based recording and export pipeline for direct Python access to color, depth, IR, point-cloud, and IMU data.
- An Open3D-based recording and export pipeline using Open3D's Azure Kinect MKV interfaces.
- Several helper scripts for camera parameter export, depth-value inspection, and simple IMU trajectory estimation.

## 2. 环境配置 / Environment Setup

中文：已在 Ubuntu 24.04 和 26.04 上验证。官方只提供 Ubuntu 18.04 的 deb 包，但在新版 Ubuntu 上可以正常安装使用。

English: Verified on Ubuntu 24.04 and 26.04. Microsoft only ships Ubuntu 18.04 deb packages, but they install and work on newer releases.

### 2.1 安装 K4A SDK / Install the K4A SDK

```bash
mkdir -p ~/azure_kinect && cd ~/azure_kinect

wget https://packages.microsoft.com/ubuntu/18.04/prod/pool/main/libk/libk4a1.4/libk4a1.4_1.4.1_amd64.deb
wget https://packages.microsoft.com/ubuntu/18.04/prod/pool/main/libk/libk4a1.4-dev/libk4a1.4-dev_1.4.1_amd64.deb
wget https://packages.microsoft.com/ubuntu/18.04/prod/pool/main/k/k4a-tools/k4a-tools_1.4.1_amd64.deb
wget http://ftp.de.debian.org/debian/pool/main/libs/libsoundio/libsoundio1_1.1.0-1_amd64.deb
wget https://raw.githubusercontent.com/microsoft/Azure-Kinect-Sensor-SDK/develop/scripts/99-k4a.rules

# 用 apt 安装可自动补齐依赖（如 libjack-jackd2-0）
# Installing with apt pulls in missing dependencies (e.g. libjack-jackd2-0)
sudo apt install ./libsoundio1_1.1.0-1_amd64.deb
sudo apt install ./libk4a1.4_1.4.1_amd64.deb ./libk4a1.4-dev_1.4.1_amd64.deb ./k4a-tools_1.4.1_amd64.deb

# udev 规则：免 sudo 访问相机 / udev rules: access the camera without sudo
sudo cp 99-k4a.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

中文：

- 安装 libk4a1.4 时会弹出 Microsoft EULA 对话框，默认选项是 No，需要用方向键或 Tab 选中 Yes 再回车，否则安装会失败。请保持该终端打开直到安装结束。
- 安装完成后拔插一次相机 USB 线，让 udev 规则生效。
- 相机必须接在 USB 3 接口上。`lsusb | grep 045e` 应能看到 Depth Camera 和 4K Camera 两个设备。
- 如果包版本发生变化，请以 Microsoft 官方文档为准。

English:

- Installing libk4a1.4 opens a Microsoft EULA dialog that defaults to No. Select Yes with the arrow or Tab keys and press Enter, or the install fails. Keep that terminal open until it finishes.
- Unplug and replug the camera afterwards so the udev rules apply.
- The camera must be on a USB 3 port. `lsusb | grep 045e` should list both the Depth Camera and the 4K Camera.
- If package versions change, prefer the Microsoft official documentation over this pinned example.

### 2.2 提高 USB 缓冲区上限 / Raise the USB Buffer Limit

中文：Linux 默认的 usbfs 缓冲区只有 16 MB，录制时会出现 `libusb ... errno=12` 并可能丢帧。建议调到 1000 MB：

English: Linux defaults to a 16 MB usbfs buffer, which triggers `libusb ... errno=12` and can drop frames. Raise it to 1000 MB:

```bash
# 立即生效 / take effect now
echo 1000 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb

# 重启后保持 / persist across reboots
echo 'GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT usbcore.usbfs_memory_mb=1000"' \
  | sudo tee /etc/default/grub.d/99-k4a-usbfs.cfg
sudo update-grub
```

### 2.3 验证设备 / Verify the Device

```bash
k4arecorder --list   # 应输出序列号和固件版本 / should print the serial number and firmware versions
k4aviewer            # Open Device → Start
```

### 2.4 Python 环境 / Python Environment

中文：pyk4a 需要编译链接 K4A SDK，所以必须先完成 2.1。建议使用独立的 conda 环境：

English: pyk4a builds against the K4A SDK, so finish 2.1 first. Use a dedicated conda environment:

```bash
conda create -n k4a python=3.10
conda activate k4a
pip install numpy opencv-python tqdm pyk4a open3d pandas scipy matplotlib
```

中文：

- pyk4a 路线需要 pyk4a。
- Open3D 路线需要 open3d（录制和读取 MKV 依赖系统中的 libk4a）。
- IMU 轨迹分析脚本需要 pandas、scipy、matplotlib。

English:

- The pyk4a workflow requires pyk4a.
- The Open3D workflow requires open3d (recording and MKV reading use the system libk4a).
- The IMU trajectory script requires pandas, scipy, and matplotlib.

## 3. 仓库结构 / Repository Layout

```text
config/                  Azure Kinect 录制配置 JSON / Azure Kinect recording configs
Configuration details/   参考文档 / reference notes
data/                    实验数据目录 / experiment data
output/                  导出结果目录 / exported outputs
video/                   录制得到的 MKV 与 IMU CSV / recorded MKV files and IMU CSVs

recorder_pyk4a.py        使用 pyk4a 录制 MKV 和 IMU / record MKV + IMU via pyk4a
export_pyk4a.py          导出深度、RGB、IR、点云、内参 / export depth, RGB, IR, point cloud, intrinsics
recorder_open3d.py       使用 Open3D 录制 MKV / record MKV via Open3D
export_open3d.py         使用 Open3D 导出彩色和深度 / export color and depth via Open3D
imu_trajectory.py        从 IMU CSV 估计轨迹 / estimate trajectory from IMU CSV
read depth.py            统计深度 .npy 数据分布 / inspect depth .npy statistics
test.py                  读取并保存深度相机内参示例 / minimal intrinsic export example
```

## 4. 配置文件 / Configuration Files

中文：仓库当前提供三组配置，彩色格式均为 MJPG：

- config/720p_NFOV_UNBINNED.json: 720P 彩色，NFOV_UNBINNED 深度，30 FPS。
- config/720p_WFOV_UNBINNED.json: 720P 彩色，WFOV_UNBINNED 深度，15 FPS。
- config/1080p_WFOV_UNBINNED.json: 1080P 彩色，WFOV_UNBINNED 深度，15 FPS。

English: The repository includes three camera presets, all with MJPG color:

- config/720p_NFOV_UNBINNED.json: 720P color, NFOV_UNBINNED depth, 30 FPS.
- config/720p_WFOV_UNBINNED.json: 720P color, WFOV_UNBINNED depth, 15 FPS.
- config/1080p_WFOV_UNBINNED.json: 1080P color, WFOV_UNBINNED depth, 15 FPS.

中文：

- WFOV_UNBINNED 模式下设备不支持超过 15 FPS，两个录制脚本都会检查这一组合。
- 两个录制脚本都会读取 `color_format`。推荐保持 MJPG：相机原生输出就是 MJPG，BGRA32 只是 SDK 在电脑上解码后的结果，画质相同；但 BGRA32 的文件约大 3 倍，录制时更耗 CPU，而且 Open3D 读不了。

English:

- WFOV_UNBINNED does not support frame rates above 15 FPS, and both recorders check for that combination.
- Both recorders honor `color_format`. Keep MJPG: the camera outputs MJPG natively and BGRA32 is just the SDK decoding it on the host, so image quality is identical, while BGRA32 files are about 3x larger, recording uses more CPU, and Open3D cannot read them.

## 5. 快速开始 / Quick Start

中文：所有脚本都使用相对路径，请在仓库根目录、并在 `k4a` 环境中运行。同一时间只能有一个程序打开相机，录制前请关闭 k4aviewer。

English: All scripts use relative paths, so run them from the repository root inside the `k4a` environment. Only one process can open the camera at a time; close k4aviewer before recording.

### 5.1 使用 pyk4a 录制 / Record with pyk4a

中文：编辑 recorder_pyk4a.py 中 main 部分的 video_name 和 config_name，需要时修改 EXPOSURE_US / AUTO_EXPOSURE，然后运行，按 Ctrl+C 停止：

English: Edit video_name and config_name in the main block of recorder_pyk4a.py, optionally set EXPOSURE_US / AUTO_EXPOSURE, then run it and press Ctrl+C to stop:

```bash
python recorder_pyk4a.py
```

中文：脚本会生成以下文件（720P + NFOV_UNBINNED 30 FPS 约 50 MB/秒，主要是未压缩的深度和 IR）：

- video/<scene>.mkv
- video/<scene>_imu.csv（约 1.6 kHz）

English: The script writes the following (about 50 MB/s at 720P + NFOV_UNBINNED 30 FPS, mostly uncompressed depth and IR):

- video/<scene>.mkv
- video/<scene>_imu.csv (about 1.6 kHz)

### 5.2 使用 pyk4a 导出 / Export with pyk4a

中文：编辑 export_pyk4a.py 中的 SCENE_NAME，然后运行。MJPG 和 BGRA32 录制都支持，缺少深度或彩色的帧会被跳过。

English: Edit SCENE_NAME in export_pyk4a.py, then run it. Both MJPG and BGRA32 recordings are supported; captures missing depth or color are skipped.

```bash
python export_pyk4a.py
```

中文：输出目录为 output/<scene>_export/，深度相关数据都在深度相机坐标系下（576×640，NFOV_UNBINNED）：

- depth_raw/: 原始深度 .npy（uint16，毫米）
- depth_vis/: 深度伪彩图 .png（每帧按 2%–98% 分位数拉伸）
- rgb_raw/: 原始彩色图 .png
- rgb_aligned/: 对齐到深度相机的彩色图 .png
- ir_raw/: 红外图 .npy
- point_cloud/: 深度点云 .npy（H×W×3，毫米）
- intrinsic_depth.txt / intrinsic_color.txt
- distortion_depth.txt / distortion_color.txt

English: The output directory is output/<scene>_export/. Depth-related data is in the depth camera frame (576×640 for NFOV_UNBINNED):

- depth_raw/: raw depth .npy files (uint16, mm)
- depth_vis/: pseudo-colored depth .png files (per-frame 2%–98% percentile stretch)
- rgb_raw/: raw color .png files
- rgb_aligned/: color reprojected into the depth camera .png files
- ir_raw/: IR .npy files
- point_cloud/: depth point-cloud .npy files (H×W×3, mm)
- intrinsic_depth.txt / intrinsic_color.txt
- distortion_depth.txt / distortion_color.txt

### 5.3 使用 Open3D 录制 / Record with Open3D

中文：编辑 recorder_open3d.py 中的 video_name 与 config_name，然后运行，按 Ctrl+C 停止：

English: Edit video_name and config_name in recorder_open3d.py, then run it and press Ctrl+C to stop:

```bash
python recorder_open3d.py
```

中文：录制结果会保存为 video/<scene>.mkv（不含 IMU CSV）。

English: The recording is saved as video/<scene>.mkv (no IMU CSV).

### 5.4 使用 Open3D 导出 / Export with Open3D

中文：编辑 export_open3d.py 中的 video_name，需要时调整顶部的 DEPTH_VIS_MIN_MM / DEPTH_VIS_MAX_MM（深度伪彩图的固定显示范围，默认 0–550 mm），然后运行：

English: Edit video_name in export_open3d.py, optionally adjust DEPTH_VIS_MIN_MM / DEPTH_VIS_MAX_MM at the top (the fixed display range of the depth colormap, 0–550 mm by default), then run:

```bash
python export_open3d.py
```

中文：输出目录为 output/<scene>/：

- color/: 彩色图像
- depth/: 原始深度 .npy 与伪彩图 .png。**Open3D 读出的深度已对齐到彩色相机**，与彩色图同分辨率，所以应搭配 K_rgb.txt 使用。
- K_rgb.txt / K_depth.txt

English: The output directory is output/<scene>/:

- color/: color images
- depth/: raw depth .npy files and pseudo-colored depth .png files. **Open3D aligns depth to the color camera**, so it has the color resolution; pair it with K_rgb.txt.
- K_rgb.txt / K_depth.txt

### 5.5 兼容性 / Compatibility

| 录制方式 / Recorded with | export_pyk4a.py | export_open3d.py |
|---|---|---|
| recorder_pyk4a.py（MJPG） | ✓ | ✓ |
| recorder_open3d.py（MJPG） | ✓ | ✓ |
| k4arecorder（默认 MJPG / MJPG by default） | ✓ | ✓ |
| 旧版 BGRA32 录制 / Legacy BGRA32 recordings | ✓ | ✗ |

## 6. 辅助脚本 / Helper Scripts

### 6.1 IMU 轨迹估计 / IMU Trajectory Estimation

中文：imu_trajectory.py 读取 IMU CSV，进行简单的陀螺积分、重力补偿和 ZUPT 静止约束，输出：

- output/imu_trajectory_est.csv
- output/imu_trajectory_est.png

English: imu_trajectory.py reads an IMU CSV file, performs simple gyro integration, gravity compensation, and a basic ZUPT heuristic, then writes:

- output/imu_trajectory_est.csv
- output/imu_trajectory_est.png

中文：运行前请先修改脚本顶部的 csv_path。脚本默认录制开始的前 2 秒相机静止，用于估计偏置。纯 IMU 二次积分漂移很大，结果只适合粗略参考。

English: Update csv_path near the top of the script before running it. The script assumes the camera is still for the first 2 seconds to estimate biases. Pure IMU double integration drifts quickly, so treat the result as a rough estimate only.

```bash
python imu_trajectory.py
```

### 6.2 深度数据检查 / Depth Data Inspection

中文：read depth.py 会遍历一个场景的深度 .npy 文件，打印每帧和整体统计量。运行前请先修改 SCENE，可以填场景名（如 `wet_open3d`、`wet_pyk4a_export`）或完整目录路径。

- 自动识别 export_open3d.py 的 `depth/` 和 export_pyk4a.py 的 `depth_raw/`，不会把 IR 和点云混进统计。
- 统计时排除无效的 0 值，并单独打印有效像素比例。

English: read depth.py scans the depth .npy files of one scene and reports per-file plus global statistics. Update SCENE before running; it accepts a scene name (e.g. `wet_open3d`, `wet_pyk4a_export`) or a full directory path.

- Detects both `depth/` (export_open3d.py) and `depth_raw/` (export_pyk4a.py), so IR and point clouds are never mixed in.
- Invalid zero pixels are excluded, and the valid-pixel ratio is reported separately.

```bash
python "read depth.py"
```

### 6.3 内参导出示例 / Intrinsic Export Example

中文：test.py 展示了如何直接通过 pyk4a 获取深度相机内参并写入文本文件。

English: test.py shows a minimal example of reading the depth-camera intrinsic matrix directly from pyk4a and saving it to a text file.

```bash
python test.py
```

## 7. K4A 命令行工具 / K4A Command-Line Tools

中文：安装 SDK 后，可以用官方工具确认设备是否工作正常。

English: After installing the SDK, use the official tools to verify the device is working.

```bash
k4arecorder --list
k4aviewer
k4aviewer -HighDPI
k4arecorder -h
k4arecorder -d NFOV_UNBINNED -c 1080p -r 5 output.mkv
```

## 8. 常见问题 / Troubleshooting

| 现象 / Symptom | 原因与解决 / Cause and fix |
|---|---|
| `LIBUSB_ERROR_BUSY` | 相机已被其他程序占用（k4aviewer、另一个录制脚本等）。关闭后重试。<br>Another process (k4aviewer, another recorder) already has the camera open. Close it and retry. |
| `libusb ... errno=12` | usbfs 缓冲区太小，见 2.2。<br>The usbfs buffer is too small; see 2.2. |
| 不用 sudo 打不开设备 / Cannot open the device without sudo | udev 规则没生效：确认 `/etc/udev/rules.d/99-k4a.rules` 存在，并拔插相机。<br>udev rules not applied: check `/etc/udev/rules.d/99-k4a.rules` exists and replug the camera. |
| apt 安装卡住 / apt install hangs | EULA 对话框在等待输入；如果终端已关闭，用 `ps aux \| grep whiptail` 找到并结束它，再重新安装。<br>The EULA dialog is waiting for input; if its terminal was closed, find it with `ps aux \| grep whiptail`, kill it, and reinstall. |
| Open3D 报 `Unexpected image format` 且导出 0 帧 / Open3D reports `Unexpected image format` and exports 0 frames | MKV 是用 BGRA32 录的，Open3D 只能读 MJPG。改用 export_pyk4a.py，或用 MJPG 重新录制。<br>The MKV was recorded as BGRA32, which Open3D cannot read. Use export_pyk4a.py or re-record with MJPG. |
| `[Warning] Frame lag` 仅出现在开头 / only at the start | 相机启动时第一帧较慢，可以忽略。<br>The first frame is slow while the camera starts; safe to ignore. |
| 日志提示固件版本偏旧 / Firmware version warning | SDK 1.4.1 推荐 RGB 1.6.110 / Depth 1.6.80，旧版本也能正常使用。<br>SDK 1.4.1 recommends RGB 1.6.110 / Depth 1.6.80; older firmware still works. |

## 9. 当前仓库的使用特点 / Current Usage Pattern in This Repository

中文：当前脚本以实验脚本风格为主，而不是通用 CLI 工具，因此有几个使用特征需要注意：

- 多数脚本在 main 中写死了场景名、配置名或输入路径。
- 输出目录命名并不完全统一，例如 Open3D 导出和 pyk4a 导出的目录结构不同，深度所在坐标系也不同（Open3D 对齐到彩色，pyk4a 保留深度相机）。
- 脚本主要面向单机、本地数据处理，没有参数解析、日志系统或批处理封装。

English: The scripts are currently written more like lab utilities than polished CLI tools, so keep these traits in mind:

- Most scripts use hard-coded scene names, config names, or input paths in the main block.
- Output naming is not fully unified: the Open3D and pyk4a export layouts differ, and so does the depth frame (Open3D aligns to color, pyk4a keeps the depth camera).
- The code is intended for local experimentation, without argument parsing, logging, or batch orchestration.

## 10. 参考资料 / References

- Azure Kinect Sensor SDK: https://github.com/microsoft/Azure-Kinect-Sensor-SDK
- pyk4a: https://github.com/etiennedub/pyk4a
- Open3D Azure Kinect docs: Configuration details/open3d_azure.markdown
- Depth mode note: Configuration details/depth_mode.markdown

## TODO LIST

中文：如果你准备继续维护这个仓库，优先建议做以下改进：

- 给 recorder/export 脚本补充命令行参数，而不是手动改源码。
- 统一 output 目录结构与命名规则。
- 增加 requirements.txt 或 environment.yml。
- 在 README 中增加示例输入、示例输出截图。

English: If you plan to keep maintaining this repository, these are the suggested next steps:

- Add command-line arguments to the recorder/export scripts instead of editing source code.
- Unify the output directory layout and naming.
- Add requirements.txt or environment.yml.
- Add sample inputs and output screenshots to the README.
