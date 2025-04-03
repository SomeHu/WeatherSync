import os
import requests
from notion_client import Client
from dotenv import load_dotenv

# Load .env config
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
KEEP_MOBILE = os.getenv("KEEP_MOBILE")
KEEP_PASSWORD = os.getenv("KEEP_PASSWORD")

# Login to Keep
login_res = requests.post("https://api.gotokeep.com/v1.1/users/login", json={
    "mobile": KEEP_MOBILE,
    "password": KEEP_PASSWORD
})
token = login_res.json().get("data", {}).get("token")

# Fetch Keep data
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "running", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})

try:
    data_raw = res.json()
    records = data_raw.get("data", {}).get("records", [])
    print("👀 提取后的 records 内容：", records)
except Exception as e:
    print("❌ JSON 解析失败：", e)
    records = []

# Initialize Notion client
notion = Client(auth=NOTION_TOKEN)

# Get existing KeepIDs to prevent duplication
existing_ids = set()
try:
    query = notion.databases.query(database_id=NOTION_DATABASE_ID)
    for page in query.get("results", []):
        prop = page["properties"].get("KeepID", {})
        if "number" in prop:
            existing_ids.add(str(prop["number"]))
    print("🪜 已存在的 KeepID：", existing_ids)
except Exception as e:
    print("⚠️ 查询 Notion 数据库失败：", e)

# Write to Notion
for group in records:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats", {})
        keep_id = stats.get("id")

        if not keep_id or str(keep_id) in existing_ids:
            print(f"⏭️ 跳过重复或无效 ID：{keep_id}")
            continue

        try:
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "名称": {"title": [{"text": {"content": stats.get("name", "未命名运动")}}]},
                    "日期": {"date": {"start": stats.get("doneDate")}},
                    "时长": {"number": stats.get("duration")},
                    "距离": {"number": stats.get("kmDistance")},
                    "卡路里": {"number": stats.get("calorie")},
                    "类型": {"rich_text": [{"text": {"content": stats.get("type", "unknown")}}]},
                    "KeepID": {"number": int(keep_id.split("_")[-1].replace("rn", "")[:8])}  # 保证数字且唯一
                }
            )
            print(f"✅ 同步成功：{keep_id}")
        except Exception as e:
            print(f"❌ 同步失败：{keep_id}，错误：{e}")

print("✅ Keep ➜ Notion 同步完成！")
