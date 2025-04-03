
import os
import requests
from notion_client import Client
from dotenv import load_dotenv

# 加载 .env 配置
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

# 获取运动数据
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "running", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})
records = res.json().get("data", {}).get("records", [])

# 查询 Notion 中已存在的 KeepID（避免重复）
existing_ids = set()
query = notion.databases.query(database_id=NOTION_DATABASE_ID)
for result in query.get("results", []):
    props = result["properties"]
    keep_id = props.get("KeepID", {}).get("rich_text", [])
    if keep_id:
        existing_ids.add(keep_id[0]["text"]["content"])

# 写入 Notion
for group in records:
    for item in group.get("logs", []):
        stats = item.get("stats", {})
        keep_id = stats.get("id")
        if keep_id in existing_ids:
            print(f"⚠️ 已存在：{keep_id}")
            continue

        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "名称": {"title": [{"text": {"content": stats.get("name", "未命名运动")}}]},
                "日期": {"date": {"start": stats.get("doneDate")}},
                "时长": {"number": stats.get("duration")},
                "距离": {"number": stats.get("kmDistance")},
                "卡路里": {"number": stats.get("calorie")},
                "类型": {"rich_text": [{"text": {"content": stats.get("type", "unknown")}}]},
                "KeepID": {"rich_text": [{"text": {"content": keep_id}}]},
                "平均心率": {"number": stats.get("heartRate", {}).get("averageHeartRate", 0)},
                "最大心率": {"number": stats.get("heartRate", {}).get("maxHeartRate", 0)},
                "平均配速": {"number": stats.get("averagePace", 0)}
            }
        )
        print(f"✅ 已写入：{keep_id}")
