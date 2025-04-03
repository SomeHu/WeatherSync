import os
import requests
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
KEEP_MOBILE = os.getenv("KEEP_MOBILE")
KEEP_PASSWORD = os.getenv("KEEP_PASSWORD")

# 登录 Keep
login_res = requests.post("https://api.gotokeep.com/v1.1/users/login", json={
    "mobile": KEEP_MOBILE,
    "password": KEEP_PASSWORD
})
token = login_res.json().get("data", {}).get("token")

if not token:
    print("❌ 获取 Keep token 失败，请检查手机号或密码")
    exit(1)

# 获取运动记录
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all",
    "type": "running",
    "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})

data = res.json().get("data", {}).get("records", [])

print("👀 提取后的 records 内容：", data)

# 初始化 Notion
notion = Client(auth=NOTION_TOKEN)

for group in data:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats", {})
        name = stats.get("name", "未命名运动")
        done_date = stats.get("doneDate")
        duration = stats.get("duration", 0)
        distance = stats.get("kmDistance", 0)
        calorie = stats.get("calorie", 0)
        workout_type = stats.get("type", "running")

        try:
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "名称": {
                        "title": [{"text": {"content": name}}]
                    },
                    "日期": {
                        "date": {"start": done_date}
                    },
                    "时长": {
                        "number": duration
                    },
                    "距离": {
                        "number": distance
                    },
                    "卡路里": {
                        "number": calorie
                    },
                    "类型": {
                        "rich_text": [{"text": {"content": workout_type}}]
                    }
                }
            )
        except Exception as e:
            print(f"⚠️ 写入 Notion 出错：{e}")

print("✅ Keep 运动数据同步完成！")
