import os
import requests
from notion_client import Client
from dotenv import load_dotenv
from datetime import datetime

# 加载环境变量
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
KEEP_MOBILE = os.getenv("KEEP_MOBILE")
KEEP_PASSWORD = os.getenv("KEEP_PASSWORD")

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
print(f"👀 想提取的总条数: {len(data)}")

# 设置 emoji 分类
TYPE_EMOJI_MAP = {
    "running": "🏃‍♂️",
    "walking": "🚶",
    "cycling": "🚴",
    "swimming": "🏊",
    "default": "🏋️"
}

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

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

        print(f"🗕️ 处理日期: {done_date}, 类型: {sport_type}, 距离: {km}")

        if page_exists(done_date, workout_id):
            continue

        # 生成标题
        title = f"{TYPE_EMOJI_MAP.get(sport_type, TYPE_EMOJI_MAP['default'])} {stats.get('name', '未命名')} {stats.get('nameSuffix', '')}"

        # 计算配速
        duration = stats.get("duration", 0)
        pace = round(duration / km, 2) if km else 0.0

        # 写入 Notion
        notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties={
            "名称": {"title": [{"text": {"content": title}}]},
            "日期": {"date": {"start": done_date}},
            "时长": {"number": duration},
            "距离": {"number": km},
            "卡路里": {"number": stats.get("calorie")},
            "类型": {"rich_text": [{"text": {"content": workout_id}}]},
            "平均配速": {"number": pace},
            "平均心率": {
                "number": stats.get("heartRate", {}).get("averageHeartRate", 0)
                if isinstance(stats.get("heartRate"), dict) else 0
            },
            "轨迹图": {
                "files": [{
                    "name": "track.jpg",
                    "external": {"url": stats.get("trackWaterMark", "")}
                }] if stats.get("trackWaterMark") else []
            }
        })

print("✅ Notion 同步完成")
