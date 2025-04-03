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

try:
    data_raw = res.json()
    records = data_raw.get("data", {}).get("records", [])
    print("👀 提取后的 records 内容：", records)
except Exception as e:
    print("❌ JSON解析失败：", e)
    records = []

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

# 遍历写入
if isinstance(records, list) and all(isinstance(g, dict) for g in records):
    for group in records:
        logs = group.get("logs", [])
        for item in logs:
            stats = item.get("stats", {})

            # 防止 None.get 报错
            heart_rate_data = stats.get("heartRate") or {}
            avg_heart_rate = heart_rate_data.get("averageHeartRate", 0)
            max_heart_rate = heart_rate_data.get("maxHeartRate", 0)

            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "名称": {"title": [{"text": {"content": stats.get("name", "未命名运动")}}]},
                    "日期": {"date": {"start": stats.get("doneDate")}},
                    "时长": {"number": stats.get("duration")},
                    "距离": {"number": stats.get("kmDistance")},
                    "卡路里": {"number": stats.get("calorie")},
                    "平均配速": {"number": stats.get("averagePace")},
                    "平均心率": {"number": avg_heart_rate},
                    "最大心率": {"number": max_heart_rate},
                    "类型": {"rich_text": [{"text": {"content": item.get("type", "unknown")}}]}
                }
            )
    print("✅ Keep 运动数据已成功同步至 Notion！")
else:
    print("⚠️ 未获取到有效的运动记录，可能是 token 无效或数据结构变化。")
