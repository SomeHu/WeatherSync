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
print("📦 Keep 原始返回内容：", data_raw)
records = data_raw.get("data", {}).get("records", [])
print("📦 提取后的 records 内容：", records)


# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

# 将数据写入 Notion
if isinstance(data, list) and all(isinstance(g, dict) for g in data):
    for group in data:
        logs = group.get("logs", [])
        for item in logs:
            stats = item.get("stats", {})
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "名称": {"title": [{"text": {"content": stats.get("display", "未命名运动")}}]},
                    "日期": {"date": {"start": stats.get("doneDate")}},
                    "时长": {"number": stats.get("duration")},
                    "距离": {"number": stats.get("kmDistance")},
                    "卡路里": {"number": stats.get("calorie")},
                    "类型": {"rich_text": [{"text": {"content": item.get("type", "unknown")}}]}
                }
            )
    print("✅ Keep 运动数据同步完成！")
else:
    print("❌ 警告：Keep 返回的数据格式不符合预期，可能登录失败或未获取到数据。")
