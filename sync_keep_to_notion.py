import os
import requests
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
KEEP_MOBILE = os.getenv("KEEP_MOBILE")
KEEP_PASSWORD = os.getenv("KEEP_PASSWORD")

notion = Client(auth=NOTION_TOKEN)

# 登录 Keep 获取 token
login_res = requests.post("https://api.gotokeep.com/v1.1/users/login", json={
    "mobile": KEEP_MOBILE,
    "password": KEEP_PASSWORD
})
token = login_res.json().get("data", {}).get("token")

# 获取所有数据类型（不限制 running）
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "all", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})

records = res.json().get("data", {}).get("records", [])
print(f"👀 汇总所有类型后的记录条数： {len(records)}")

# 简化 emoji 映射
TYPE_EMOJI_MAP = {
    "running": "🏃",
    "walking": "🚶",
    "cycling": "🚴",
    "default": "💪"
}

def is_duplicate(done_date):
    query = notion.databases.query(
        **{
            "database_id": NOTION_DATABASE_ID,
            "filter": {
                "property": "日期",
                "date": {"equals": done_date}
            }
        }
    )
    return len(query.get("results", [])) > 0

for group in records:
    for item in group.get("logs", []):
        stats = item.get("stats", {})
        if not stats:
            continue

        done_date = stats.get("doneDate")
        if is_duplicate(done_date):
            print(f"⚠️ 已存在：{done_date}，跳过")
            continue

        sport_type = stats.get("type", "default")
        emoji = TYPE_EMOJI_MAP.get(sport_type, TYPE_EMOJI_MAP["default"])
        title = f"{emoji} {stats.get('name', '未命名')}{stats.get('nameSuffix', '')}"

        # 创建 Notion 页面
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "名称": {"title": [{"text": {"content": title}}]},
                "日期": {"date": {"start": done_date}},
                "类型": {"rich_text": [{"text": {"content": sport_type}}]},
                "时长": {"number": stats.get("duration")},
                "距离": {"number": stats.get("kmDistance")},
                "卡路里": {"number": stats.get("calorie")},
                "配速": {"number": stats.get("averagePace")},
                "平均心率": {
                    "number": stats.get("heartRate", {}).get("averageHeartRate", 0) if stats.get("heartRate") else 0
                },
                "轨迹图": {
                    "files": [{
                        "name": "track.jpg",
                        "type": "external",
                        "external": {"url": stats.get("trackWaterMark")}
                    }] if stats.get("trackWaterMark") else []
                }
            }
        )

print("✅ 同步完成！")
