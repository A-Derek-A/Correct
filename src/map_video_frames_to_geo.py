import argparse
from pathlib import Path

import pandas as pd


def map_frames_to_geo(
    video_path: Path,
    excel_path: Path,
    first_timestamp_ms: int,
    fps: float,
    ts_column: str = "时间戳",
    lat_column: str = "target_lat_deg",
    lon_column: str = "target_lon_deg",
    out_path: Path | None = None,
) -> Path:
    """
    根据第一帧时间戳和帧率，将视频每一帧映射到
    ZTMK011-卫星地理高度_姿态计算视线经纬度.xlsx 中最近的经纬度。

    假设:
    - Excel 中时间戳列为毫秒级 Unix 时间 (UTC)
    - 每一秒有一行经纬度 (1 Hz)，列名为 lat_column / lon_column
    """
    if out_path is None:
        out_path = video_path.with_suffix(".frames_geo.xlsx")

    df_geo = pd.read_excel(excel_path)
    if ts_column not in df_geo.columns:
        raise KeyError(
            f"Excel 中找不到时间戳列 {ts_column!r}，实际列名为: {list(df_geo.columns)}"
        )
    for col in (lat_column, lon_column):
        if col not in df_geo.columns:
            raise KeyError(
                f"Excel 中找不到列 {col!r}，实际列名为: {list(df_geo.columns)}"
            )

    df_geo = df_geo[[ts_column, lat_column, lon_column]].copy()
    df_geo = df_geo.sort_values(ts_column).reset_index(drop=True)

    # 获取视频帧数；如果没有安装 opencv-python，则要求用户手动指定总帧数
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - 依赖环境
        raise RuntimeError(
            "需要 opencv-python 来读取视频帧数。"
            " 请先执行 `pip install opencv-python`，"
            " 或者自己写脚本统计帧数后改用本脚本的逻辑。"
        ) from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频文件: {video_path}")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    # 为每一帧生成时间戳 (ms)
    frame_indices = list(range(frame_count))
    frame_ts_ms = [
        first_timestamp_ms + int(round(i * 1000.0 / fps)) for i in frame_indices
    ]

    df_frames = pd.DataFrame(
        {
            "frame_index": frame_indices,
            "frame_ts_ms": frame_ts_ms,
        }
    )
    df_frames = df_frames.sort_values("frame_ts_ms")

    # 使用 merge_asof 将每一帧时间映射到最近的 1Hz 经纬度记录
    merged = pd.merge_asof(
        df_frames,
        df_geo.rename(columns={ts_column: "geo_ts_ms"}),
        left_on="frame_ts_ms",
        right_on="geo_ts_ms",
        direction="nearest",
    )

    merged.to_excel(out_path, index=False)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="根据第一帧时间戳和帧率，为视频每一帧匹配最近的经纬度。"
    )
    parser.add_argument(
        "--video",
        required=True,
        help="视频文件路径，例如 data/Beijing/JMS301_...dat.mp4",
    )
    parser.add_argument(
        "--excel",
        default="data/new_data/ZTMK011-卫星地理高度_姿态计算视线经纬度.xlsx",
        help="包含时间戳+经纬度的 Excel，默认为新数据文件。",
    )
    parser.add_argument(
        "--first-timestamp-ms",
        type=int,
        required=True,
        help="视频第一帧的时间戳（毫秒级 Unix 时间，UTC）。",
    )
    parser.add_argument(
        "--fps",
        type=float,
        required=True,
        help="视频帧率 (frames per second)。",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="输出 Excel 文件路径，默认与视频同名加 .frames_geo.xlsx。",
    )

    args = parser.parse_args()

    video_path = Path(args.video)
    excel_path = Path(args.excel)
    out_path = Path(args.out) if args.out is not None else None

    result = map_frames_to_geo(
        video_path=video_path,
        excel_path=excel_path,
        first_timestamp_ms=args.first_timestamp_ms,
        fps=args.fps,
        out_path=out_path,
    )

    print(f"每帧经纬度匹配完成，结果已写入: {result}")


if __name__ == "__main__":
    main()

