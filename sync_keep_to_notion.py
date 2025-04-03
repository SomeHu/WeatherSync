
code = '''
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

# 获取运动数据（所有类型）
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "all", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})


try:
    data_raw = res.json()
    records = data_raw.get("data", {}).get("records", [])
    print(f"👀 汇总所有类型后的记录条数： {len(records)}")
except Exception as e:
    print("❌ 解析 JSON 出错：", e)
    records = []

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

# 类型 emoji 映射
TYPE_EMOJI_MAP = {
    "running": "🏃",
    "walking": "🚶",
    "cycling": "🚴",
    "swimming": "🏊",
    "badminton": "🏸",
    "basketball": "🏀",
    "yoga": "🧘",
    "ropeSkipping": "🤾",
    "default": "🏋️"
}

# 去重缓存（可扩展为读取 Notion 现有数据避免重复）
existing_ids = set()

# 同步到 Notion
for group in records:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats")
        if not stats:
            continue

        workout_id = stats.get("id")
        if workout_id in existing_ids:
            continue
        existing_ids.add(workout_id)

        sport_type = stats.get("type", "unknown")
        emoji = TYPE_EMOJI_MAP.get(sport_type, TYPE_EMOJI_MAP["default"])
        title = f"{emoji} {stats.get('name', '未命名')} {stats.get('nameSuffix', '')}"

        try:
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "名称": {"title": [{"text": {"content": title}}]},
                    "类型": {"rich_text": [{"text": {"content": sport_type}}]},
                    "日期": {"date": {"start": stats.get("doneDate")}},
                    "时长": {"number": stats.get("duration")},
                    "距离": {"number": stats.get("kmDistance")},
                    "卡路里": {"number": stats.get("calorie")},
                    "平均配速": {"number": stats.get("averagePace", 0)},
                    "平均心率": {"number": stats.get("heartRate", {}).get("averageHeartRate", 0)},
                }
            )
        except Exception as e:
            print(f"❌ 写入 Notion 失败：{e}")

print("✅ Keep 数据同步完成")
'''
