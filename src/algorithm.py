import numpy as np
import math
from skyfield.api import EarthSatellite, load, wgs84

def calculate_target_lonlat(tle_line1, tle_line2, altitude_m, roll_deg, pitch_deg, yaw_deg, obs_time=None):
    """
    根据 TLE、实测高度和姿态角计算卫星视线与地面的交点经纬度。
    
    参数:
        tle_line1 (str): TLE 第一行
        tle_line2 (str): TLE 第二行
        altitude_m (float): 卫星实测地理高度 (单位: 米)
        roll_deg (float): 横滚角 (绕X轴/前进方向, 单位: 度)
        pitch_deg (float): 俯仰角 (绕Y轴/右侧方向, 单位: 度)
        yaw_deg (float): 偏航角 (绕Z轴/地心方向, 单位: 度)
        obs_time (skyfield.timelib.Time, optional): 观测时间。默认使用当前时间。
        
    返回:
        tuple: (目标点经度, 目标点纬度) 单位: 度
    """
    ts = load.timescale()
    if obs_time is None:
        obs_time = ts.now()
        
    satellite = EarthSatellite(tle_line1, tle_line2, 'TargetSat', ts)
    
    geocentric = satellite.at(obs_time)
    subpoint = wgs84.subpoint(geocentric)
    lat0_rad = subpoint.latitude.radians
    lon0_rad = subpoint.longitude.radians
    

    obs_time_plus_1s = ts.utc(obs_time.utc_datetime().year, 
                              obs_time.utc_datetime().month, 
                              obs_time.utc_datetime().day, 
                              obs_time.utc_datetime().hour, 
                              obs_time.utc_datetime().minute, 
                              obs_time.utc_datetime().second + 1)
    
    subpoint_next = wgs84.subpoint(satellite.at(obs_time_plus_1s))
    lat1_rad = subpoint_next.latitude.radians
    lon1_rad = subpoint_next.longitude.radians
    
    dlon = lon1_rad - lon0_rad
    y_heading = math.sin(dlon) * math.cos(lat1_rad)
    x_heading = math.cos(lat0_rad) * math.sin(lat1_rad) - math.sin(lat0_rad) * math.cos(lat1_rad) * math.cos(dlon)
    heading_rad = math.atan2(y_heading, x_heading) # 航向角 (相对正北，顺时针)
    
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    
    # 根据 Z-Y-X 旋转顺序，推导视线 [0,0,1]^T 旋转后的向量
    v_ox = math.cos(yaw)*math.sin(pitch)*math.cos(roll) + math.sin(yaw)*math.sin(roll)
    v_oy = math.sin(yaw)*math.sin(pitch)*math.cos(roll) - math.cos(yaw)*math.sin(roll)
    v_oz = math.cos(pitch)*math.cos(roll)
    
    # 确保视线是朝向地面的（v_oz 必须大于 0）
    if v_oz <= 0:
        raise ValueError("姿态角过大，视线未指向地面！")
        
    # 假设我们地面处于平坦地面，计算视线在地面的偏移(单位: 米) 因为地面可能有山或者沟壑，地球也不是完美的球体，之后可以修正，或许可以考虑记住两帧之间的地理高度，进行校正。
    delta_x = altitude_m * (v_ox / v_oz)  # 前方偏移
    delta_y = altitude_m * (v_oy / v_oz)  # 右侧偏移
    
    # 根据轨道的升角，将这种便宜旋转至北东坐标系，方便我们对经纬度计算
    delta_n = delta_x * math.cos(heading_rad) - delta_y * math.sin(heading_rad)
    delta_e = delta_x * math.sin(heading_rad) + delta_y * math.cos(heading_rad)
    
    R_e = 6371000.0
    
    lat_target_rad = lat0_rad + (delta_n / R_e)
    lon_target_rad = lon0_rad + (delta_e / (R_e * math.cos(lat0_rad)))
    
    target_lat_deg = math.degrees(lat_target_rad)
    target_lon_deg = math.degrees(lon_target_rad)
    
    return target_lon_deg, target_lat_deg

