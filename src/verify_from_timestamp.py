import pandas as pd
from pathlib import Path

from skyfield.api import EarthSatellite, load


# 原始数据文件（与之前保持一致）
DATA_PATH = Path("data/Beijing/ZTMK011-卫星地理高度.xlsx")

# 列名（根据你提供的信息）
TS_COLUMN = "时间戳"
HEIGHT_COLUMN = "参数值"  # 假定单位与之前一致（通常是 km）

# TLE（与 correct.py 中保持一致，NORAD_ID = 66997）
TLE_LINE1 = "1 66997U 25292E   26067.96574883  .00006598  00000+0  46089-3 0  9995"
TLE_LINE2 = "2 66997  97.6387 144.7098 0014305 347.9988  12.0895 15.05591511 13353"


def load_from_timestamp(excel_path: Path) -> pd.DataFrame:
    df = pd.read_excel(excel_path)

    for col in (TS_COLUMN, HEIGHT_COLUMN):
        if col not in df.columns:
            raise KeyError(
                f"Excel 中找不到列 {col!r}，实际列名为: {list(df.columns)}"
            )

    df = df.copy()

    # 假定“时间戳”是 Unix 时间（秒），并且本身就是以 UTC 计的时间
    # 如果你的时间戳实际是毫秒，改成 unit="ms" 即可
    df["utc_time"] = pd.to_datetime(df[TS_COLUMN], unit="ms", utc=True)

    return df


def compute_tle_altitudes_from_utc(df: pd.DataFrame, time_col: str) -> pd.Series:
    ts = load.timescale()
    satellite = EarthSatellite(TLE_LINE1, TLE_LINE2, "SAT", ts)

    times = []
    for t in df[time_col]:
        # t 是 pandas 的 Timestamp（带 UTC 时区），先转成 python datetime
        t = pd.to_datetime(t).to_pydatetime()
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

    return pd.Series(tle_alt_km, index=df.index, name="tle_alt_km_ts")


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"找不到数据文件: {DATA_PATH}")

    # 1. 基于时间戳 -> UTC 计算 TLE 高度
    df = load_from_timestamp(DATA_PATH)
    tle_alt_km_ts = compute_tle_altitudes_from_utc(df, "utc_time")

    measured_alt_km = df[HEIGHT_COLUMN].astype(float)

    df["tle_alt_km_ts"] = tle_alt_km_ts
    df["alt_diff_km_ts"] = measured_alt_km - df["tle_alt_km_ts"]

    # Excel 不支持带时区的时间，这里去掉 tz，只保留 UTC 时间值
    df["utc_time"] = df["utc_time"].dt.tz_localize(None)

    # 2. 如果之前已经有基于 BJT 的对比结果，则读入并做差值比较
    bjt_result_path = DATA_PATH.with_name(DATA_PATH.stem + "_tle对比结果.xlsx")
    if bjt_result_path.exists():
        df_bjt = pd.read_excel(bjt_result_path)

        # 这里假定之前脚本输出里有一列 'alt_diff_km'，并且可以通过“时间戳”对齐
        # 如果你更希望按“时间（BJT）”对齐，可以改成用该列 merge
        if "alt_diff_km" in df_bjt.columns and TS_COLUMN in df_bjt.columns:
            merged = pd.merge(
                df[[TS_COLUMN, "alt_diff_km_ts"]],
                df_bjt[[TS_COLUMN, "alt_diff_km"]],
                on=TS_COLUMN,
                how="inner",
                suffixes=("_ts", "_bjt"),
            )

            merged["alt_diff_delta_km"] = (
                merged["alt_diff_km_ts"] - merged["alt_diff_km"]
            )

            compare_out = DATA_PATH.with_name(
                DATA_PATH.stem + "_两种时间源高度差对比.xlsx"
            )
            merged.to_excel(compare_out, index=False)
            print(f"已生成两种时间源的高度差对比文件: {compare_out}")

    out_path = DATA_PATH.with_name(
        DATA_PATH.stem + "_timestamp_utc_tle对比结果.xlsx"
    )
    df.to_excel(out_path, index=False)

    print(f"基于时间戳(UTC) 的对比完成，结果已写入: {out_path}")
    print(
        "基于时间戳的差值统计(单位 km): "
        f"mean={df['alt_diff_km_ts'].mean():.6f}, "
        f"std={df['alt_diff_km_ts'].std():.6f}, "
        f"min={df['alt_diff_km_ts'].min():.6f}, "
        f"max={df['alt_diff_km_ts'].max():.6f}"
    )


if __name__ == "__main__":
    main()

