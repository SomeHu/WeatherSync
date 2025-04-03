import os
import requests
from notion_client import Client
from dotenv import load_dotenv

# 读取 .env 环境变量
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

# 请求返回数据
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "running", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})

try:
    data_raw = res.json()
    records = data_raw.get("data", {}).get("records", [])
    print("👀 提取后的 records 内容：", records)
except Exception as e:
    print("❌ 解析 JSON 失败：", e)
    records = []

# Notion 初始化
notion = Client(auth=NOTION_TOKEN)

# 开始各条记录的转换和导入
for group in records:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats", {})
        heart_rate_info = stats.get("heartRate") or {}
        vendor_info = stats.get("vendor") or {}

        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "名称": {"title": [{"text": {"content": stats.get("name", "未命名运动")}}]},
                "日期": {"date": {"start": stats.get("doneDate")}},
                "时长": {"number": stats.get("duration", 0)},
                "距离": {"number": stats.get("kmDistance", 0)},
                "卡路里": {"number": stats.get("calorie", 0)},
                "类型": {"rich_text": [{"text": {"content": item.get("type", "unknown")}}]},
                "来源": {"rich_text": [{"text": {"content": vendor_info.get("deviceModel", vendor_info.get("source", "Keep"))}}]},
                "平均心率": {"number": heart_rate_info.get("averageHeartRate", 0)},
                "最大心率": {"number": heart_rate_info.get("maxHeartRate", 0)},
                "平均配速": {"number": stats.get("averagePace", 0)}
            }
        )

print("✅ Keep 数据同步到 Notion 完成！")
