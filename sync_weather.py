import os
import requests
from notion_client import Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from collections import Counter

# 加载环境变量
load_dotenv()

# 环境变量
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY_ID = os.getenv("CITY_ID", "1806691")  # 衡阳市：1806691

if not all([NOTION_TOKEN, NOTION_DATABASE_ID, OPENWEATHER_API_KEY]):
    print("缺少环境变量！请检查 NOTION_TOKEN, NOTION_DATABASE_ID 和 OPENWEATHER_API_KEY 是否设置。")
    exit(1)

# Notion 客户端
notion = Client(auth=NOTION_TOKEN)

# 时区
beijing_tz = pytz.timezone('Asia/Shanghai')

def get_beijing_date(dt_utc=None):
    """返回北京时间的 YYYY-MM-DD 字符串；若传入 dt_utc（UTC datetime），则转为北京日期。"""
    if dt_utc is None:
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        beijing_now = utc_now.astimezone(beijing_tz)
        return beijing_now.strftime('%Y-%m-%d')
    else:
        beijing = dt_utc.astimezone(beijing_tz)
        return beijing.strftime('%Y-%m-%d')

def get_weather(city_id):
    """当前天气（实况）"""
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?id={city_id}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_cn"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        resp = requests.get(weather_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("cod") == 200:
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            return f"{desc} ~ {temp}°C"
        else:
            return f"天气请求失败: {data.get('message', '未知错误')}"
    except requests.exceptions.RequestException as e:
        print(f"天气请求失败: {e}")
        return "无法获取天气信息"

def get_tomorrow_forecast(city_id):
    """
    5天/3小时预报，提取“明天”的切片，输出摘要：
    - 明天的最低/最高温
    - 最常见天气概况（众数描述）
    - 可选：中午/下午段的代表温度
    """
    url = f"http://api.openweathermap.org/data/2.5/forecast?id={city_id}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_cn"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("cod") not in ("200", 200):
            return f"预报请求失败: {data.get('message', '未知错误')}"

        # OpenWeather 返回的 dt 是 UTC 秒；city.timezone 给出城市相对 UTC 的秒偏移
        tz_offset_seconds = data.get("city", {}).get("timezone", 0)

        # 计算“明天”的北京日期字符串
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        beijing_now = utc_now.astimezone(beijing_tz)
        beijing_tomorrow = (beijing_now + timedelta(days=1)).date().strftime('%Y-%m-%d')

        temps = []
        descs = []
        midday_candidates = []  # 用于找“中午~下午”的代表温度（本地时间 12-15 点）
        for item in data.get("list", []):
            dt_utc = datetime.utcfromtimestamp(item["dt"]).replace(tzinfo=pytz.utc)
            # 将 UTC 转为北京时区
            dt_bj = dt_utc.astimezone(beijing_tz)
            date_bj = dt_bj.strftime('%Y-%m-%d')

            if date_bj == beijing_tomorrow:
                temp = item["main"]["temp"]
                desc = item["weather"][0]["description"]
                temps.append(temp)
                descs.append(desc)

                if 12 <= dt_bj.hour <= 15:
                    midday_candidates.append(temp)

        if not temps:
            return "暂无明日预报数据"

        t_min = round(min(temps), 1)
        t_max = round(max(temps), 1)
        # 选一个最常见天气描述
        most_common_desc = Counter(descs).most_common(1)[0][0]
        # 中午代表温度（如果没有命中，就用均值）
        if midday_candidates:
            rep_temp = round(sum(midday_candidates) / len(midday_candidates), 1)
        else:
            rep_temp = round(sum(temps) / len(temps), 1)

        return f"{most_common_desc}，{t_min}~{t_max}°C（白天约 {rep_temp}°C）"

    except requests.exceptions.RequestException as e:
        print(f"预报请求失败: {e}")
        return "无法获取明日预报"

def create_weather_page():
    today = get_beijing_date()
    now_weather = get_weather(CITY_ID)
    tomorrow_forecast = get_tomorrow_forecast(CITY_ID)

    title = f"🌤️ {today} 天气"

    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "名称": {"title": [{"text": {"content": title}}]},
                "日期": {"date": {"start": today}},
                "天气": {"rich_text": [{"text": {"content": now_weather}}] if now_weather else []},
                "明日预报": {"rich_text": [{"text": {"content": tomorrow_forecast}}] if tomorrow_forecast else []},

                # 以下字段保留你的原始结构（数值用 0 占位，兼容你现有数据库的 schema）
                "时长": {"number": 0},
                "距离": {"number": 0},
                "卡路里": {"number": 0},
                "类型": {"rich_text": [{"text": {"content": "天气同步"}}]},
                "平均配速": {"number": 0},
                "平均心率": {"number": 0},
                "数据来源": {"rich_text": [{"text": {"content": "手动同步"}}]}
            }
        )
        print(f"✅ 已同步天气数据: {today} - {title}")
    except Exception as e:
        print(f"⛔ 同步失败: {today} - {title}, 错误: {str(e)}")

if __name__ == "__main__":
    create_weather_page()
