import os
import requests
from notion_client import Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
KEEP_MOBILE = os.getenv("KEEP_MOBILE")
KEEP_PASSWORD = os.getenv("KEEP_PASSWORD")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")  # 新增天气 API KEY

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

# 登录 Keep 获取 token
login_res = requests.post("https://api.gotokeep.com/v1.1/users/login", json={
    "mobile": KEEP_MOBILE,
    "password": KEEP_PASSWORD
})
token = login_res.json().get("data", {}).get("token")

# 请求 Keep 运动数据
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})
data = res.json().get("data", {}).get("records", [])
print(f"👀 汇总所有类型后的记录条数： {len(data)}")

# 设置 emoji 分类
TYPE_EMOJI_MAP = {
    "running": "🏃‍♂️",
    "walking": "🚶",
    "cycling": "🚴",
    "swimming": "🏊",
    "default": "🏋️"
}

# 查询天气函数（模拟城市：上海）
def query_weather(date_str):
    try:
        date = date_str.split("T")[0]
        url = f"https://devapi.qweather.com/v7/historical/weather?location=101020100&date={date}&key={WEATHER_API_KEY}"
        r = requests.get(url)
        d = r.json().get("weatherDaily", [{}])[0]
        return f"{d.get('textDay', '未知')} {d.get('tempMin', '')}~{d.get('tempMax', '')}°C"
    except:
        return "未知"

# 去重辅助函数
def page_exists(done_date, workout_id):
    query = notion.databases.query(
        **{
            "database_id": NOTION_DATABASE_ID,
            "filter": {
                "and": [
                    {"property": "日期", "date": {"equals": done_date}},
                    {"property": "类型", "rich_text": {"contains": workout_id}}
                ]
            }
        }
    )
    return len(query.get("results", [])) > 0

# 开始处理每条记录
for group in data:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats")
        if not stats:
            continue

        done_date = stats.get("doneDate", "")
        if not done_date.startswith("2025"):
            continue

        sport_type = stats.get("type", "unknown")
        workout_id = stats.get("id", "")
        km = stats.get("kmDistance", 0.0)

        print(f"📅 当前处理日期: {done_date}, 类型: {sport_type}, 距离: {km}")

        if page_exists(done_date, workout_id):
            continue

        title = f"{TYPE_EMOJI_MAP.get(sport_type, TYPE_EMOJI_MAP['default'])} {stats.get('name', '未命名')} {stats.get('nameSuffix', '')}"

        duration = stats.get("duration", 0)
        pace_seconds = int(duration / km) if km > 0 else 0

        hr = stats.get("heartRate")
        avg_hr = hr.get("averageHeartRate", 0) if isinstance(hr, dict) else 0

        vendor = stats.get("vendor", {})
        source = vendor.get("source", "Keep")
        device = vendor.get("deviceModel", "")
        vendor_display = f"{source} {device}".strip()

        weather = query_weather(done_date)

        notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties={
            "名称": {"title": [{"text": {"content": title}}]},
            "日期": {"date": {"start": done_date}},
            "时长": {"number": duration},
            "距离": {"number": km},
            "卡路里": {"number": stats.get("calorie")},
            "类型": {"rich_text": [{"text": {"content": workout_id}}]},
            "平均配速": {"number": pace_seconds},
            "平均心率": {"number": avg_hr},
            "数据来源": {"rich_text": [{"text": {"content": vendor_display}}]},
            "天气": {"rich_text": [{"text": {"content": weather}}]},
            "轨迹图": {
                "files": [{
                    "name": "track.jpg",
                    "external": {"url": stats.get("trackWaterMark", "")}
                }] if stats.get("trackWaterMark") else []
            }
        })

print("✅ 已完成 Notion 同步")
