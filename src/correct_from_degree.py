import math
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from algorithm import calculate_target_lonlat_from_pos

# 数据文件路径
DATA_DIR = Path("data/03-13")
DATA_LON = DATA_DIR / "ZTMK009-卫星地理经度longitude.xlsx"
DATA_LAT = DATA_DIR / "ZTMK010-卫星地理纬度latitude.xlsx"
DATA_ALT = DATA_DIR / "ZTMK011-卫星地理高度.xlsx"
DATA_ATT_X = DATA_DIR / "ZTMK021-轨道系姿态角x.xlsx"
DATA_ATT_Y = DATA_DIR / "ZTMK022-轨道系姿态角y.xlsx"
DATA_ATT_Z = DATA_DIR / "ZTMK023-轨道系姿态角z.xlsx"

# 列名
TS_COLUMN = "时间戳"
VAL_COLUMN = "参数值"


def read_param(path: Path, col_name: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    for col in (TS_COLUMN, VAL_COLUMN):
        if col not in df.columns:
            raise KeyError(f"{path.name} 中找不到列 {col!r}，实际列名为: {list(df.columns)}")
    return df[[TS_COLUMN, VAL_COLUMN]].rename(columns={VAL_COLUMN: col_name})


def build_merged_df() -> pd.DataFrame:
    for p in (DATA_LON, DATA_LAT, DATA_ALT, DATA_ATT_X, DATA_ATT_Y, DATA_ATT_Z):
        if not p.exists():
            raise FileNotFoundError(f"找不到数据文件: {p}")

    df_lon = read_param(DATA_LON, "sat_lon_deg")
    df_lat = read_param(DATA_LAT, "sat_lat_deg")
    df_alt = read_param(DATA_ALT, "altitude_val")
    df_x   = read_param(DATA_ATT_X, "roll_deg")
    df_y   = read_param(DATA_ATT_Y, "pitch_deg")
    df_z   = read_param(DATA_ATT_Z, "yaw_deg")

    df = df_lon
    for other in (df_lat, df_alt, df_x, df_y, df_z):
        df = df.merge(other, on=TS_COLUMN, how="inner")

    df["utc_time"] = pd.to_datetime(df[TS_COLUMN], unit="ms", utc=True)

    # 下一时刻的位置，用于计算航向角；最后一行用前一行的方向
    df["next_sat_lon_deg"] = df["sat_lon_deg"].shift(-1)
    df["next_sat_lat_deg"] = df["sat_lat_deg"].shift(-1)
    df.iloc[-1, df.columns.get_loc("next_sat_lon_deg")] = df["sat_lon_deg"].iloc[-2]
    df.iloc[-1, df.columns.get_loc("next_sat_lat_deg")] = df["sat_lat_deg"].iloc[-2]

    return df


def main() -> None:
    df = build_merged_df()

    target_lons = []
    target_lats = []
    invalid_flags = []

    it = zip(
        df["sat_lon_deg"],
        df["sat_lat_deg"],
        df["next_sat_lon_deg"],
        df["next_sat_lat_deg"],
        df["altitude_val"],
        df["roll_deg"],
        df["pitch_deg"],
        df["yaw_deg"],
    )

    for sat_lon, sat_lat, next_lon, next_lat, alt_val, roll_deg, pitch_deg, yaw_deg in tqdm(
        list(it), total=len(df), desc="计算相机视线指向"
    ):
        altitude_m = float(alt_val) * 1000  # km -> m

        try:
            lon, lat = calculate_target_lonlat_from_pos(
                sat_lon_deg=float(sat_lon),
                sat_lat_deg=float(sat_lat),
                next_sat_lon_deg=float(next_lon),
                next_sat_lat_deg=float(next_lat),
                altitude_m=altitude_m,
                roll_deg=float(roll_deg),
                pitch_deg=float(pitch_deg),
                yaw_deg=float(yaw_deg),
            )
        except ValueError:
            target_lons.append(math.nan)
            target_lats.append(math.nan)
            invalid_flags.append(True)
            continue

        target_lons.append(lon)
        target_lats.append(lat)
        invalid_flags.append(False)

    df["target_lon_deg"] = target_lons
    df["target_lat_deg"] = target_lats
    df["attitude_invalid"] = invalid_flags

    df["utc_time"] = df["utc_time"].dt.tz_localize(None)

    out_path = DATA_DIR / (DATA_ALT.stem + "_姿态计算视线经纬度.xlsx")
    df.to_excel(out_path, index=False)
    invalid_count = sum(invalid_flags)
    print(f"计算完成，结果已写入: {out_path}")
    print(f"其中姿态角过大被跳过的样本数: {invalid_count}")


if __name__ == "__main__":
    main()
