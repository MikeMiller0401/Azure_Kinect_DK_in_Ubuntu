import open3d as o3d
import time
import os
import json

def init_config(config_path):
    # Load Azure Kinect Sensor Config
    config = o3d.io.read_azure_kinect_sensor_config(config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = json.load(f)
        
    fps_string = config_dict.get("camera_fps", "")
    fps = int(fps_string.split('_')[-1])

    resolution_string = config_dict.get("color_resolution", "")
    resolution = resolution_string.split('_')[-1]

    depth_mode_string = config_dict.get("depth_mode", "")
    depth_mode = depth_mode_string.split('_')[3] + '_' + depth_mode_string.split('_')[4]
    print('='*80)
    print(f"The camera has {fps} FPS, {resolution} resolution, and {depth_mode} depth mode")
    print('='*80)
    if fps > 15 and depth_mode == "WFOV_UNBINNED":
        raise RuntimeError("The camera does not support higher than 15 FPS in WFOV_UNBINNED mode.")
    return config, fps

def init_recorder(config):
    # Initialize recorder
    recorder = o3d.io.AzureKinectRecorder(config, 0)
    recorder.init_sensor()
    return recorder

def record(recorder, video_name, fps):
    os.makedirs("video", exist_ok=True)
    mkv_path = os.path.join("video", video_name + ".mkv")
    if not recorder.open_record(mkv_path):
        raise RuntimeError(f"Failed to open {mkv_path} for recording")
    TARGET_FPS = fps
    FRAME_DURATION = 1.0 / TARGET_FPS
    print('='*80)
    print(f"Start recording... Press Ctrl+C to stop")
    print('='*80)
    # --- 【新增：初始化计数器和总开始时间】 ---
    frame_count = 0
    recording_start_time = time.time() 

    try:
        while True:
            start_time = time.time()  # 记录当前帧开始时间

            # 抓取并写入这一帧（返回值不使用，所以不做深度对齐，省掉每帧的计算）
            recorder.record_frame(
                enable_record=True,
                enable_align_depth_to_color=False
            )
            
            # --- 【新增：累加帧数并计算总录制时长】 ---
            frame_count += 1
            total_duration = time.time() - recording_start_time
            
            # 使用 \r 实现单行原地刷新，end="" 防止换行
            print(f"\rRecording: Frame {frame_count:05d} | Time: {total_duration:.2f}s", end="", flush=True)

            # 计算这一帧处理花了多少时间
            elapsed_time = time.time() - start_time
            
            # 动态计算需要 sleep 多少时间才能对齐目标帧率
            sleep_time = FRAME_DURATION - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # 如果掉帧，换行打印警告，避免弄乱原本的原地刷新行
                print(f"\n[Warning] Frame processing lag! Cost: {elapsed_time:.4f}s")

    except KeyboardInterrupt:
        print("\nStopping recording...")  # 捕获异常后先换行，防止覆盖计数输出
    finally:
        recorder.close_record()
    print(f"Saved to {mkv_path}")
    

if __name__ == "__main__":
    video_name = "wet_open3d"
    config_name = "720p_NFOV_UNBINNED"
    # config_name = "720p_WFOV_UNBINNED"
    config_path = os.path.join("config", config_name + ".json")
    config, fps = init_config(config_path)
    recorder = init_recorder(config)
    record(recorder, video_name, fps)
    