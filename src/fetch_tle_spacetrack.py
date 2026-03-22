import os
import argparse
import requests
from datetime import datetime
from pathlib import Path


LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
# TLE 查询接口，使用 basicspacedata/query
TLE_URL_TEMPLATE = (
    # "https://www.space-track.org/basicspacedata/query/"
    # "class/tle/NORAD_CAT_ID/{norad_id}/EPOCH/{start}--{end}/format/tle"

    "https://www.space-track.org/basicspacedata/query/"
    "class/gp_history/NORAD_CAT_ID/{norad_id}/EPOCH/{start}--{end}/format/tle"
)
WORK_PATH = Path(__file__).parent.parent
DATA_PATH = WORK_PATH / "data" / "TLE"


def fetch_tle(norad_id: int, start_date: str, end_date: str, out_path: str) -> None:
    """
    从 space-track.org 获取指定 NORAD_ID 和时间范围的 TLE，并保存为 .tle 文件。

    参数:
        norad_id: NORAD_CAT_ID，例如 66997
        start_date: 起始日期，格式 YYYY-MM-DD（UTC）
        end_date: 结束日期，格式 YYYY-MM-DD（UTC）
        out_path: 输出文件路径，例如 '66997_2025-02-01_2025-02-02.tle'
    """
    # 简单校验日期格式
    for d in (start_date, end_date):
        datetime.strptime(d, "%Y-%m-%d")

    username = os.getenv("SPACETRACK_USER")
    password = os.getenv("SPACETRACK_PASS")

    if not username or not password:
        raise RuntimeError(
            "请先在环境变量中设置 SPACETRACK_USER 和 SPACETRACK_PASS，"
            "例如：\n"
            "  export SPACETRACK_USER='1710555219@qq.com'\n"
            "  export SPACETRACK_PASS='你的密码'\n"
        )

    with requests.Session() as s:
        # 1. 登录
        resp = s.post(
            LOGIN_URL,
            data={"identity": username, "password": password},
            timeout=30,
        )
        resp.raise_for_status()

        # 2. 构造 TLE 查询 URL
        url = TLE_URL_TEMPLATE.format(
            norad_id=norad_id,
            start=start_date,
            end=end_date,
        )

        resp = s.get(url, timeout=60)
        resp.raise_for_status()

        tle_text = resp.text.strip()
        if not tle_text:
            raise RuntimeError("指定时间范围内未返回任何 TLE。")
        
        with open(DATA_PATH / out_path, "w", encoding="utf-8") as f:
            f.write(tle_text + "\n")

        print(f"TLE 已保存到: {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="从 space-track.org 下载指定 NORAD_ID 和日期范围的 TLE（.tle 文件）"
    )
    parser.add_argument(
        "--norad-id",
        type=int,
        default=66997,
        help="NORAD_CAT_ID，默认 66997",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="起始日期，格式 YYYY-MM-DD，例如 2025-02-01",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="结束日期，格式 YYYY-MM-DD，例如 2025-02-02",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="输出 .tle 文件名，默认自动按参数生成",
    )
    args = parser.parse_args()

    out = args.out
    if out is None:
        out = f"{args.norad_id}_{args.start}_{args.end}.tle"

    fetch_tle(args.norad_id, args.start, args.end, out)


if __name__ == "__main__":
    main()