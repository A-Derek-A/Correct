import math
from pathlib import Path

import pandas as pd
from skyfield.api import EarthSatellite, load
from tqdm import tqdm

from algorithm import calculate_target_lonlat

# 数据文件路径
DATA_DIR = Path("data/03-13")
DATA_ALT   = DATA_DIR / "ZTMK011-卫星地理高度.xlsx"
DATA_ATT_X = DATA_DIR / "ZTMK021-轨道系姿态角x.xlsx"
DATA_ATT_Y = DATA_DIR / "ZTMK022-轨道系姿态角y.xlsx"
DATA_ATT_Z = DATA_DIR / "ZTMK023-轨道系姿态角z.xlsx"

# TLE 文件（给定日期范围内 NORAD 66997 的多组 TLE）
TLE_FILE = Path("data/TLE/66997_2026-03-13_2026-03-14.tle")

# 列名
TS_COLUMN  = "时间戳"
VAL_COLUMN = "参数值"

# 缓存：从 TLE 文件解析出的 (epoch_time, line1, line2) 列表
_TLE_ENTRIES: list[tuple] | None = None


def _load_tle_entries(ts) -> list[tuple]:
    """
    从 TLE_FILE 读取多组 TLE，返回列表:
    [(epoch_time, line1, line2), ...]
    其中 epoch_time 是 skyfield 的 Time 对象，便于与 obs_time 做时间差比较。
    """
    entries: list[tuple] = []
    if not TLE_FILE.exists():
        raise FileNotFoundError(f"找不到 TLE 文件: {TLE_FILE}")

    with TLE_FILE.open("r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]

    # 典型 .tle 文件按 name / line1 / line2 三行为一组
    i = 0
    while i + 2 <= len(lines):
        if not lines[i].startswith("1 ") and not lines[i].startswith("2 "):
            name  = lines[i]
            line1 = lines[i + 1]
            line2 = lines[i + 2]
            i += 3
        else:
            name  = "SAT"
            line1 = lines[i]
            line2 = lines[i + 1]
            i += 2

        sat = EarthSatellite(line1, line2, name, ts)
        entries.append((sat.epoch, line1, line2))

    if not entries:
        raise ValueError(f"TLE 文件 {TLE_FILE} 中没有解析出任何 TLE 记录。")

    return entries


def _get_nearest_tle_lines(ts, obs_time) -> tuple[str, str]:
    """在缓存的 TLE 列表中找到与 obs_time 最接近的一组 TLE 行。"""
    global _TLE_ENTRIES
    if _TLE_ENTRIES is None:
        _TLE_ENTRIES = _load_tle_entries(ts)

    best_line1, best_line2 = None, None
    best_dt = None
    for epoch, line1, line2 in _TLE_ENTRIES:
        dt_seconds = abs(float(obs_time - epoch) * 86400.0)
        if best_dt is None or dt_seconds < best_dt:
            best_dt = dt_seconds
            best_line1, best_line2 = line1, line2

    assert best_line1 is not None and best_line2 is not None
    return best_line1, best_line2


def read_param(path: Path, col_name: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    for col in (TS_COLUMN, VAL_COLUMN):
        if col not in df.columns:
            raise KeyError(f"{path.name} 中找不到列 {col!r}，实际列名为: {list(df.columns)}")
    return df[[TS_COLUMN, VAL_COLUMN]].rename(columns={VAL_COLUMN: col_name})


def build_merged_df() -> pd.DataFrame:
    for p in (DATA_ALT, DATA_ATT_X, DATA_ATT_Y, DATA_ATT_Z):
        if not p.exists():
            raise FileNotFoundError(f"找不到数据文件: {p}")

    df_alt = read_param(DATA_ALT,   "altitude_val")
    df_x   = read_param(DATA_ATT_X, "roll_deg")
    df_y   = read_param(DATA_ATT_Y, "pitch_deg")
    df_z   = read_param(DATA_ATT_Z, "yaw_deg")

    df = df_alt
    for other in (df_x, df_y, df_z):
        df = df.merge(other, on=TS_COLUMN, how="inner")

    df["utc_time"] = pd.to_datetime(df[TS_COLUMN], unit="ms", utc=True)
    return df


def main() -> None:
    df = build_merged_df()
    ts = load.timescale()

    target_lons  = []
    target_lats  = []
    invalid_flags = []

    it = zip(
        df["utc_time"],
        df["altitude_val"],
        df["roll_deg"],
        df["pitch_deg"],
        df["yaw_deg"],
    )

    for utc_ts, alt_val, roll_deg, pitch_deg, yaw_deg in tqdm(
        list(it), total=len(df), desc="计算相机视线指向（TLE）"
    ):
        dt = pd.to_datetime(utc_ts).to_pydatetime()
        obs_time = ts.utc(
            dt.year, dt.month, dt.day,
            dt.hour, dt.minute,
            dt.second + dt.microsecond / 1e6,
        )

        altitude_m = float(alt_val) * 1000  # km -> m
        line1, line2 = _get_nearest_tle_lines(ts, obs_time)

        try:
            lon, lat = calculate_target_lonlat(
                line1, line2,
                altitude_m=altitude_m,
                roll_deg=float(roll_deg),
                pitch_deg=float(pitch_deg),
                yaw_deg=float(yaw_deg),
                obs_time=obs_time,
            )
        except ValueError:
            target_lons.append(math.nan)
            target_lats.append(math.nan)
            invalid_flags.append(True)
            continue

        target_lons.append(lon)
        target_lats.append(lat)
        invalid_flags.append(False)

    df["target_lon_deg"]  = target_lons
    df["target_lat_deg"]  = target_lats
    df["attitude_invalid"] = invalid_flags

    df["utc_time"] = df["utc_time"].dt.tz_localize(None)

    out_path = DATA_DIR / (DATA_ALT.stem + "_姿态计算视线经纬度.xlsx")
    df.to_excel(out_path, index=False)
    invalid_count = sum(invalid_flags)
    print(f"计算完成，结果已写入: {out_path}")
    print(f"其中姿态角过大被跳过的样本数: {invalid_count}")


if __name__ == "__main__":
    main()
