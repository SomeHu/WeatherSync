import os
import requests
from notion_client import Client
from dotenv import load_dotenv

# 加载 .env 环境变量
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

# 获取运动数据
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "running", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})
data_raw = res.json()
records = data_raw.get("data", {}).get("records", [])
print("\U0001f440 提取后的 records 内容：", records)

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

# 定义一个已经存在的 KeepID 集合，用于判断重复
existing_ids = set()
search_res = notion.databases.query(database_id=NOTION_DATABASE_ID)
for page in search_res.get("results", []):
    keep_id = page.get("properties", {}).get("KeepID", {}).get("rich_text", [])
    if keep_id:
        existing_ids.add(keep_id[0]["text"]["content"])

# 写入 Notion 数据
for group in records:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats", {})
        keep_id = stats.get("id")
        if keep_id in existing_ids:
            print(f"⚠️ 重复，跳过 KeepID: {keep_id}")
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
            }
        )
        print(f"✅ 已同步: {keep_id} - {stats.get('name')}")

print("✨ 同步完成")
