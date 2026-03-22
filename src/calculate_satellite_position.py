#!/usr/bin/env python3
"""
根据TLE文件计算指定时间的卫星经纬度坐标
"""
from pathlib import Path
from skyfield.api import EarthSatellite, load, wgs84

# TLE文件路径
TLE_FILE = Path("data/TLE/66997_2026-03-17_2026-03-18.tle")

def load_tle_entries(ts):
    """
    从TLE文件读取多组TLE，返回列表:
    [(epoch_time, line1, line2), ...]
    """
    entries = []
    if not TLE_FILE.exists():
        raise FileNotFoundError(f"找不到TLE文件: {TLE_FILE}")

    with TLE_FILE.open("r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]

    # 解析TLE条目（每两行为一组）
    i = 0
    while i + 1 < len(lines):
        if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            line1 = lines[i]
            line2 = lines[i + 1]
            name = "SAT"
            sat = EarthSatellite(line1, line2, name, ts)
            entries.append((sat.epoch, line1, line2))
            i += 2
        else:
            i += 1

    if not entries:
        raise ValueError(f"TLE文件 {TLE_FILE} 中没有解析出任何TLE记录。")

    return entries


def get_nearest_tle_lines(ts, target_time):
    """
    在TLE列表中找到与target_time最接近的一组TLE行。
    """
    entries = load_tle_entries(ts)
    
    best_line1, best_line2 = None, None
    best_dt = None
    
    for epoch, line1, line2 in entries:
        # 计算时间差（秒）
        dt_days = target_time - epoch
        dt_seconds = abs(float(dt_days) * 86400.0)
        if best_dt is None or dt_seconds < best_dt:
            best_dt = dt_seconds
            best_line1, best_line2 = line1, line2

    assert best_line1 is not None and best_line2 is not None
    print(f"使用时间差最小的TLE（时间差: {best_dt:.2f}秒）")
    return best_line1, best_line2


def calculate_satellite_position(target_time_str):
    """
    计算指定时间的卫星经纬度坐标
    
    参数:
        target_time_str: 目标时间字符串，格式: "YYYY-MM-DD HH:MM:SS UTC"
    
    返回:
        tuple: (经度, 纬度, 高度_km)
    """
    ts = load.timescale()
    
    # 解析目标时间
    # 格式: "2026-02-02 03:24:59 UTC"
    parts = target_time_str.replace(" UTC", "").split()
    date_part = parts[0]  # "2026-02-02"
    time_part = parts[1]  # "03:24:59"
    
    year, month, day = map(int, date_part.split("-"))
    hour, minute, second = map(int, time_part.split(":"))
    
    target_time = ts.utc(year, month, day, hour, minute, second)
    
    # 获取最接近的TLE
    line1, line2 = get_nearest_tle_lines(ts, target_time)
    
    # 创建卫星对象
    satellite = EarthSatellite(line1, line2, "SAT", ts)
    
    # 计算卫星位置
    geocentric = satellite.at(target_time)
    subpoint = wgs84.subpoint(geocentric)
    
    longitude = subpoint.longitude.degrees
    latitude = subpoint.latitude.degrees
    elevation_km = subpoint.elevation.km
    
    return longitude, latitude, elevation_km


def main():
    # target_time = "2026-02-02 08:43:31 UTC"
    # target_time = "2026-03-01 05:08:50 UTC"
    # target_time = "2026-03-17 05:08:50 UTC"
    target_time = "2026-03-17 07:12:00 UTC"
    
    print(f"计算时间: {target_time}")
    print(f"TLE文件: {TLE_FILE}")
    print("-" * 50)
    
    try:
        lon, lat, alt_km = calculate_satellite_position(target_time)
        
        print(f"\n卫星位置计算结果:")
        print(f"经度: {lon:.6f}°")
        print(f"纬度: {lat:.6f}°")
        print(f"高度: {alt_km:.3f} km")
        
    except Exception as e:
        print(f"错误: {e}")
        raise


if __name__ == "__main__":
    main()
