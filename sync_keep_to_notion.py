import os
import requests
from notion_client import Client
from dotenv import load_dotenv
import json

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

# 获取运动记录
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "running", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})

try:
    data_raw = res.json()
    records = data_raw.get("data", {}).get("records", [])
    print("👀 提取后的 records 内容：", records)
except Exception as e:
    print("❌ 解析 Keep 返回内容失败：", e)
    records = []

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

# 写入 Notion
for group in records:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats", {})
        try:
            properties = {
                "名称": {"title": [{"text": {"content": stats.get("name", "未命名运动")}}]},
                "日期": {"date": {"start": stats.get("doneDate")}},
                "距离": {"number": stats.get("kmDistance")},
                "卡路里": {"number": stats.get("calorie")},
                "类型": {"rich_text": [{"text": {"content": stats.get("type", "unknown")}}]},
                "时长": {"number": stats.get("duration")}
            }

            print("📤 正在写入数据到 Notion：", json.dumps(properties, ensure_ascii=False, indent=2))

            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties=properties
            )

        except Exception as e:
            print("❌ 写入 Notion 时出错：", e)
            print("🧾 当前记录数据为：", json.dumps(properties, ensure_ascii=False, indent=2))

print("✅ 同步完成")
