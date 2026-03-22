import math
import numpy as np
from scipy.optimize import minimize
from skyfield.api import load, EarthSatellite, wgs84


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

# ==========================================
# 反推标定程序
# ==========================================
def calibrate_boresight(tle_line1, tle_line2, altitude_m, roll_deg, pitch_deg, yaw_deg, obs_time, true_lon, true_lat):
    """
    利用已知真实经纬度，反推 Roll 和 Pitch 的安装偏移角
    """
    print(f"原始姿态 - Roll: {roll_deg:.4f}, Pitch: {pitch_deg:.4f}, Yaw: {yaw_deg:.4f}")
    print(f"目标真实经纬度 - Lon: {true_lon}, Lat: {true_lat}")
    
    # 目标函数：计算加入补偿角后，算出的经纬度与真实经纬度的误差
    def cost_function(offsets):
        d_roll, d_pitch = offsets
        
        # 使用你原本的函数，将偏移角加进去
        calc_lon, calc_lat = calculate_target_lonlat(
            tle_line1, tle_line2, altitude_m, 
            roll_deg + d_roll, 
            pitch_deg + d_pitch, 
            yaw_deg, # 忽略 Yaw 的微小贡献
            obs_time
        )
        
        # 计算误差 (使用考虑了纬度收敛的近似球面距离平方)
        d_lat = calc_lat - true_lat
        d_lon = (calc_lon - true_lon) * math.cos(math.radians(true_lat))
        
        error = d_lat**2 + d_lon**2
        return error

    # 初始猜测的偏移角：[delta_roll, delta_pitch]
    initial_guess = [0.0, 0.0]
    
    # 使用 Nelder-Mead 单纯形算法进行无导数优化
    print("\n正在通过 scipy.optimize 寻找最佳补偿角...")
    result = minimize(cost_function, initial_guess, method='Nelder-Mead', tol=1e-8)
    
    if result.success:
        best_d_roll, best_d_pitch = result.x
        print("\n✅ 反推成功！")
        print(f"求得 Roll 最佳补偿角 (delta_roll):  {best_d_roll:+.6f} 度")
        print(f"求得 Pitch 最佳补偿角 (delta_pitch): {best_d_pitch:+.6f} 度")
        
        # 验证一下
        final_lon, final_lat = calculate_target_lonlat(
            tle_line1, tle_line2, altitude_m, 
            roll_deg + best_d_roll, 
            pitch_deg + best_d_pitch, 
            yaw_deg, 
            obs_time
        )
        print(f"\n应用补偿角后算出的经纬度: {final_lon:.6f}, {final_lat:.6f}")
        print(f"与真实经纬度的残差: Lon {final_lon - true_lon:+.6f}, Lat {final_lat - true_lat:+.6f}")
        
        return best_d_roll, best_d_pitch
    else:
        print("优化失败:", result.message)
        return None, None

# ==========================================
# 执行测试 (请填入你的真实 TLE 数据)
# ==========================================
if __name__ == "__main__":
    ts = load.timescale()
    # 注意：请务必替换成你当时的 TLE 数据！因为反推极其依赖轨道的准确位置
    # TLE_1 = "1 12345U 20001A   26060.21446759  .00000000  00000-0  00000-0 0  9999"
    # TLE_2 = "2 12345  97.0000   0.0000 0001000   0.0000   0.0000 15.00000000000000"
    TLE_1 = "1 66997U 25292E   26060.18962750  .00004126  00000-0  29047-3 0  9997"
    TLE_2 = "2 66997  97.6420 137.0090 0014945  16.7880 343.3839 15.05509326 12181"
    
    # 构建你的 UTC 时间
    obs_time = ts.utc(2026, 3, 1, 5, 8, 50)
    
    alt_m = 551000.0
    r_deg = 5.855553
    p_deg = 0.35171378
    y_deg = -0.016941246
    
    # 你提供的两组坐标
    calc_lat, calc_lon = 44.6039993643619, 89.089679396802   # 仅作参考，算法内部会重算
    true_lat, true_lon = 44.66315984766051, 89.10659174450721
    
    calibrate_boresight(TLE_1, TLE_2, alt_m, r_deg, p_deg, y_deg, obs_time, true_lon, true_lat)