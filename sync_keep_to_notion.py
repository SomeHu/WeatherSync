import os
import requests
from notion_client import Client
from dotenv import load_dotenv
from datetime import datetime

# 加载 .env 配置
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
KEEP_MOBILE = os.getenv("KEEP_MOBILE")
KEEP_PASSWORD = os.getenv("KEEP_PASSWORD")

# emoji & 类型映射
TYPE_EMOJI_MAP = {
    "running": "🏃‍♂️",
    "walking": "🚶‍♀️",
    "cycling": "🚴",
    "ropeSkipping": "🤾",
    "workout": "🏋️",
    "default": "🏃"
}

# 登录 Keep 获取 token
login_res = requests.post("https://api.gotokeep.com/v1.1/users/login", json={
    "mobile": KEEP_MOBILE,
    "password": KEEP_PASSWORD
})
token = login_res.json().get("data", {}).get("token")

# 拉取多个类型的运动数据
SUPPORTED_TYPES = ["running", "walking", "cycling", "ropeSkipping", "workout"]
all_records = []

for sport_type in SUPPORTED_TYPES:
    print(f"📥 正在拉取类型：{sport_type}")
    res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
        "dateUnit": "all", "type": sport_type, "lastDate": 0
    }, headers={"Authorization": f"Bearer {token}"})
    if res.ok:
        records = res.json().get("data", {}).get("records", [])
        for record in records:
            for log in record.get("logs", []):
                log["sport_type"] = sport_type
        all_records.extend(records)
    else:
        print(f"❌ 拉取 {sport_type} 数据失败：", res.text)

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)
print("👀 汇总所有类型后的记录条数：", len(all_records))

# 写入 Notion
existing_titles = set()

for group in all_records:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats", {})
        sport_type = item.get("sport_type", "default")
        title = f"{TYPE_EMOJI_MAP.get(sport_type, TYPE_EMOJI_MAP['default'])} {stats.get('name', '未命名')} {stats.get('nameSuffix', '')}"

        # 去重判断
        unique_id = stats.get("id", "")
        if unique_id in existing_titles:
            continue
        existing_titles.add(unique_id)

        try:
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "名称": {"title": [{"text": {"content": title}}]},
                    "日期": {"date": {"start": stats.get("doneDate")}},
                    "时长": {"number": stats.get("duration", 0)},
                    "距离": {"number": stats.get("kmDistance", 0)},
                    "卡路里": {"number": stats.get("calorie", 0)},
                    "类型": {"rich_text": [{"text": {"content": sport_type}}]},
                    "平均心率": {"number": (stats.get("heartRate") or {}).get("averageHeartRate", 0)},
                    "配速": {"rich_text": [{"text": {"content": f"{stats.get('averagePace', 0)} 秒/公里"}}]}
                }
            )
        except Exception as e:
            print(f"❌ 同步失败：{e}")

print("✅ 所有运动数据同步完成！")
