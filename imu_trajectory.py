import os
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
import matplotlib.pyplot as plt

csv_path = "video/holes_wet_30p_imu.csv"
df = pd.read_csv(csv_path)

# 1) 读取数据
t = df["acc_timestamp_usec"].to_numpy(dtype=np.float64) * 1e-6  # s
acc = df[["acc_x", "acc_y", "acc_z"]].to_numpy(dtype=np.float64)  # m/s^2
gyr = df[["gyro_x", "gyro_y", "gyro_z"]].to_numpy(dtype=np.float64)  # rad/s

dt = np.diff(t, prepend=t[0])
dt[0] = np.median(dt[1:])

# 2) 用前2秒估计静止段偏置（默认开始时静止）
static_mask = (t - t[0]) < 2.0
if static_mask.sum() < 50:
    static_mask = np.arange(len(t)) < min(500, len(t))

acc_mean = acc[static_mask].mean(axis=0)
gyr_bias = gyr[static_mask].mean(axis=0)

# 重力大小估计（比硬编码9.81更稳）
g_mag = np.linalg.norm(acc_mean)

# 3) 姿态初始化：把初始重力方向对齐到世界系 z 轴负方向
z_world = np.array([0.0, 0.0, -1.0])
a0_dir = acc_mean / (np.linalg.norm(acc_mean) + 1e-12)
v_cross = np.cross(a0_dir, z_world)
c = np.dot(a0_dir, z_world)
s = np.linalg.norm(v_cross)
if s < 1e-8:
    q = R.identity()
else:
    vx = np.array([
        [0, -v_cross[2], v_cross[1]],
        [v_cross[2], 0, -v_cross[0]],
        [-v_cross[1], v_cross[0], 0]
    ])
    rot_mat = np.eye(3) + vx + vx @ vx * ((1 - c) / (s**2))
    q = R.from_matrix(rot_mat)

# 4) 主循环：陀螺积分 + 重力补偿 + 积分
N = len(t)
pos = np.zeros((N, 3), dtype=np.float64)
vel = np.zeros((N, 3), dtype=np.float64)

g_world = np.array([0.0, 0.0, -g_mag])

# 静止判定阈值，可按数据微调
acc_thresh = 0.15 * g_mag        # | |a|-g | < 约1.5 m/s^2（根据噪声可收紧）
gyr_thresh = 0.03                # rad/s

for i in range(1, N):
    dti = dt[i]

    # 4.1 陀螺去偏置后积分姿态
    w = gyr[i] - gyr_bias
    dq = R.from_rotvec(w * dti)
    q = q * dq

    # 4.2 加速度转世界系并去重力
    a_world = q.apply(acc[i])
    a_lin = a_world - g_world

    # 4.3 ZUPT（静止则速度归零）
    is_static = (abs(np.linalg.norm(acc[i]) - g_mag) < acc_thresh) and (np.linalg.norm(w) < gyr_thresh)
    if is_static:
        vel[i] = np.zeros(3)
    else:
        vel[i] = vel[i-1] + a_lin * dti

    # 4.4 位置积分
    pos[i] = pos[i-1] + vel[i] * dti

# 5) 导出轨迹
os.makedirs("output", exist_ok=True)
out = pd.DataFrame({
    "t": t - t[0],
    "x": pos[:, 0],
    "y": pos[:, 1],
    "z": pos[:, 2],
    "vx": vel[:, 0],
    "vy": vel[:, 1],
    "vz": vel[:, 2],
})
out.to_csv("output/imu_trajectory_est.csv", index=False)
print("Saved: output/imu_trajectory_est.csv")

# 6) 简单可视化
fig = plt.figure(figsize=(7, 6))
ax = fig.add_subplot(111, projection="3d")
ax.plot(pos[:, 0], pos[:, 1], pos[:, 2], lw=1.0)
ax.set_xlabel("X (m)")
ax.set_ylabel("Y (m)")
ax.set_zlabel("Z (m)")
ax.set_title("IMU Integrated Trajectory (with basic ZUPT)")
plt.tight_layout()
plt.savefig("output/imu_trajectory_est.png", dpi=300)