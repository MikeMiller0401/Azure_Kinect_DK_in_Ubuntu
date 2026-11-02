"""
Print per-frame and global statistics of exported depth .npy files (zeros excluded).
统计导出的深度 .npy 数据分布（排除无效的 0 值）。

  python "read depth.py" wet_pyk4a                  # output/wet_pyk4a/{pyk4a,open3d}/
  python "read depth.py" wet_pyk4a --method open3d
  python "read depth.py" output/wet_pyk4a/pyk4a/depth
"""
import argparse
from pathlib import Path

import numpy as np


def find_depth_files(root: Path):
    return sorted(p for p in root.glob("*.npy") if p.is_file())


# depth/: export_pyk4a.py（深度相机坐标系）；depth_aligned/: export_open3d.py（彩色相机坐标系）
# depth_raw/ 和 <scene>_export/ 是旧版目录结构，仍然兼容
DEPTH_SUBDIRS = ("depth", "depth_aligned", "depth_raw")
METHODS = ("pyk4a", "open3d")


def find_depth_subdir(directory: Path):
    for name in DEPTH_SUBDIRS:
        if (directory / name).is_dir():
            return directory / name
    return None


def find_in_scene(scene_dir: Path, method):
    """Look for output/<scene>/<method>/depth*, falling back to the legacy layouts."""
    for m in ([method] if method else METHODS):
        sub = find_depth_subdir(scene_dir / m)
        if sub is not None:
            return sub
    if method is None:
        return find_depth_subdir(scene_dir)
    return None


def resolve_depth_root(scene_or_path: str, method=None) -> Path:
    # 只返回深度子目录，避免把 ir/、point_cloud/ 里的 .npy 混进统计
    input_path = Path(scene_or_path)
    if input_path.is_dir():
        if input_path.name in DEPTH_SUBDIRS:
            return input_path
        sub = find_depth_subdir(input_path) or find_in_scene(input_path, method)
        if sub is not None:
            return sub

    for scene_dir in (Path("output") / scene_or_path, Path("output") / f"{scene_or_path}_export"):
        sub = find_in_scene(scene_dir, method)
        if sub is not None:
            return sub

    output_dir = Path("output")
    available_scenes = sorted(
        p.name for p in output_dir.iterdir() if p.is_dir() and find_in_scene(p, None) is not None
    ) if output_dir.is_dir() else []
    raise FileNotFoundError(
        f"找不到场景或目录: {scene_or_path}. 可用场景: {', '.join(available_scenes)}"
    )


def main():
    parser = argparse.ArgumentParser(description="Depth .npy statistics for an exported scene.")
    parser.add_argument("scene", nargs="?", default="holes_dry_30p",
                        help="scene name under output/ or a directory path")
    parser.add_argument("--method", choices=METHODS, default=None,
                        help="which export to read when a scene has both (default: pyk4a first)")
    args = parser.parse_args()

    root = resolve_depth_root(args.scene, args.method)
    print(f"Depth directory: {root}")

    depth_files = find_depth_files(root)
    if not depth_files:
        print(f"在目录 {root} 下未找到 .npy 深度图")
        return

    global_min = None
    global_max = None
    global_min_file = None
    global_max_file = None
    total_sum = 0.0
    total_count = 0
    total_pixels = 0
    file_means = []
    file_medians = []

    for fp in depth_files:
        depth = np.load(fp)
        rel = fp.relative_to(root)
        total_pixels += int(depth.size)
        # 0 表示无效深度，不参与统计
        valid = depth[depth > 0]
        if valid.size == 0:
            print(f"{rel}: 没有有效深度")
            continue
        min_val = float(np.min(valid))
        max_val = float(np.max(valid))
        median_val = float(np.median(valid))
        mean_val = float(np.mean(valid))
        valid_ratio = valid.size / depth.size
        print(f"{rel}: min={min_val}, max={max_val}, median={median_val}, mean={mean_val:.1f}, valid={valid_ratio:.1%}")

        total_sum += float(np.sum(valid, dtype=np.float64))
        total_count += int(valid.size)
        file_means.append(mean_val)
        file_medians.append(median_val)

        if global_min is None or min_val < global_min:
            global_min = min_val
            global_min_file = rel
        if global_max is None or max_val > global_max:
            global_max = max_val
            global_max_file = rel

    print("=" * 80)
    print(f"总文件数: {len(depth_files)}")
    if total_count == 0:
        print("所有文件都没有有效深度")
        return
    print(f"有效像素比例: {total_count / total_pixels:.1%}（以下统计均已排除 0 值）")
    print(f"全局最小值: {global_min} (文件: {global_min_file})")
    print(f"全局最大值: {global_max} (文件: {global_max_file})")
    print(f"全局平均值(所有有效像素): {total_sum / total_count}")
    print(f"按帧平均值(每帧mean再平均): {float(np.mean(file_means))}")
    print(f"按帧中位数(每帧median再平均): {float(np.mean(file_medians))}")


if __name__ == "__main__":
    main()