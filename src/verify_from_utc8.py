import pandas as pd
from pathlib import Path

from skyfield.api import EarthSatellite, load


DATA_PATH = Path("data/Beijing/ZTMK011-卫星地理高度.xlsx")

# 按照实际表头修改下面两项
TIME_COLUMN = "时间（BJT）"  # Excel 表头是北京时间，需要换算成 UTC
HEIGHT_COLUMN = '参数值'  # 高度列名，单位假定为米

# 在这里填入要对比的 TLE（两行）
TLE_LINE1 = "1 66997U 25292E   26067.96574883  .00006598  00000+0  46089-3 0  9995"
TLE_LINE2 = "2 66997  97.6387 144.7098 0014305 347.9988  12.0895 15.05591511 13353"


def load_measured_altitudes(
    excel_path: Path, time_col: str, height_col: str
) -> pd.DataFrame:
    df = pd.read_excel(excel_path)
    if time_col not in df.columns:
        raise KeyError(f"Excel 中找不到时间列 {time_col!r}，实际列名为: {list(df.columns)}")
    if height_col not in df.columns:
        raise KeyError(f"Excel 中找不到高度列 {height_col!r}，实际列名为: {list(df.columns)}")

    df = df.copy()
    # Excel 中给的是北京时间（BJT = UTC+8），先按本地时间解析，再转换到 UTC
    dt_local = pd.to_datetime(df[time_col], errors="raise")
    dt_bjt = dt_local.dt.tz_localize("Asia/Shanghai")
    # 转成 UTC 供 skyfield 使用
    df[time_col] = dt_bjt.dt.tz_convert("UTC")
    return df


def compute_tle_altitudes(df: pd.DataFrame, time_col: str) -> pd.Series:
    if TLE_LINE1.startswith("PUT_YOUR") or TLE_LINE2.startswith("PUT_YOUR"):
        raise ValueError("请先在 TLE_LINE1 / TLE_LINE2 中填入真实 TLE。")

    ts = load.timescale()
    satellite = EarthSatellite(TLE_LINE1, TLE_LINE2, "SAT", ts)

    times = []
    for t in df[time_col]:
        t = pd.to_datetime(t).to_pydatetime()
        # 这里假定 Excel 时间是 UTC，如果是其它时区需要先转换
        times.append(
            ts.utc(
                t.year,
                t.month,
                t.day,
                t.hour,
                t.minute,
                t.second + t.microsecond / 1e6,
            )
        )

    tle_alt_km = []
    for t in times:
        sp = satellite.at(t).subpoint()
        tle_alt_km.append(sp.elevation.km)

    return pd.Series(tle_alt_km, index=df.index, name="tle_alt_km")


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"找不到数据文件: {DATA_PATH}")

    # 这里传入的是列名本身（字符串），不要做任何乘法
    df = load_measured_altitudes(DATA_PATH, TIME_COLUMN, HEIGHT_COLUMN)

    tle_alt_km = compute_tle_altitudes(df, TIME_COLUMN)

    # 假定 Excel 中“参数值”这一列单位是米，这里统一换算成 km
    measured_alt_km = df[HEIGHT_COLUMN].astype(float)

    df["tle_alt_km"] = tle_alt_km
    df["alt_diff_km"] = measured_alt_km - df["tle_alt_km"]

    # Excel 不支持带时区的时间，这里在导出前去掉 timezone 信息，只保留 UTC 时间数值
    df[TIME_COLUMN] = df[TIME_COLUMN].dt.tz_localize(None)

    out_path = DATA_PATH.with_name(DATA_PATH.stem + "_tle对比结果.xlsx")
    df.to_excel(out_path, index=False)

    print(f"对比完成，结果已写入: {out_path}")
    print(
        "差值统计(单位 km): "
        f"mean={df['alt_diff_km'].mean():.6f}, "
        f"std={df['alt_diff_km'].std():.6f}, "
        f"min={df['alt_diff_km'].min():.6f}, "
        f"max={df['alt_diff_km'].max():.6f}"
    )


if __name__ == "__main__":
    main()

