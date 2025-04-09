import os
import requests
from notion_client import Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 从环境变量获取配置信息
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
KEEP_MOBILE = os.getenv("KEEP_MOBILE")
KEEP_PASSWORD = os.getenv("KEEP_PASSWORD")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY_ID = os.getenv("CITY_ID", "1798082")  # 默认城市：北京，城市 ID 可替换为你的城市 ID

# 检查环境变量
if not all([NOTION_TOKEN, NOTION_DATABASE_ID, KEEP_MOBILE, KEEP_PASSWORD, OPENWEATHER_API_KEY]):
    print("缺少环境变量！请检查 NOTION_TOKEN, NOTION_DATABASE_ID, KEEP_MOBILE, KEEP_PASSWORD 和 OPENWEATHER_API_KEY 是否设置。")
    exit(1)

# 调试环境变量
print(f"NOTION_TOKEN: {NOTION_TOKEN}")
print(f"OPENWEATHER_API_KEY: {OPENWEATHER_API_KEY}")
print(f"City ID: {CITY_ID}")

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

# 登录 Keep 获取 token
login_res = requests.post("https://api.gotokeep.com/v1.1/users/login", json={
    "mobile": KEEP_MOBILE,
    "password": KEEP_PASSWORD
})
login_res.raise_for_status()  # 确保请求成功
token = login_res.json().get("data", {}).get("token")

# 请求 Keep 运动数据
res = requests.get("https://api.gotokeep.com/pd/v3/stats/detail", params={
    "dateUnit": "all", "type": "", "lastDate": 0
}, headers={"Authorization": f"Bearer {token}"})
res.raise_for_status()  # 确保请求成功
data = res.json().get("data", {}).get("records", [])
print(f"\U0001f440 汇总所有类型后的记录条数： {len(data)}")

# 天气信息获取函数
def get_weather(city_id):
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?id={city_id}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_cn"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    print(f"Weather API URL: {weather_url}")  # 调试 URL
    try:
        response = requests.get(weather_url, headers=headers)
        response.raise_for_status()  # 确保请求成功
        weather_data = response.json()
        if weather_data.get("cod") == 200:
            temperature = weather_data["main"]["temp"]
            description = weather_data["weather"][0]["description"]
            return f"{description} ~ {temperature}°C"
        else:
            return f"天气请求失败: {weather_data.get('message', '未知错误')}"
    except requests.exceptions.RequestException as e:
        print(f"天气请求失败: {e}")
        return "无法获取天气信息"

# 判断是否已经同步过此记录
def page_exists(done_date, workout_id):
    query = notion.databases.query(
        **{
            "database_id": NOTION_DATABASE_ID,
            "filter": {
                "and": [
                    {"property": "日期", "date": {"equals": done_date}},
                    {"property": "类型", "rich_text": {"contains": workout_id}}
                ]
            }
        }
    )
    return len(query.get("results", [])) > 0

# 运动记录同步
for group in data:
    logs = group.get("logs", [])
    for item in logs:
        stats = item.get("stats")
        if not stats:
            continue
        done_date = stats.get("doneDate", "")
        sport_type = stats.get("type", "unknown")
        workout_id = stats.get("id", "")
        km = stats.get("kmDistance", 0.0)

        print(f"\U0001f4c5 当前处理日期: {done_date}, 类型: {sport_type}, 距离: {km}")

        if page_exists(done_date, workout_id):
            continue

        # 获取天气信息
        weather_info = get_weather(CITY_ID)
        print(f"Weather for {done_date}: {weather_info}")

        # 创建页面标题
        title = f"🏃‍♂️ {stats.get('name', '未命名')} {stats.get('nameSuffix', '')}"
        duration = stats.get("duration", 0)
        pace_seconds = int(duration / km) if km > 0 else 0
        hr = stats.get("heartRate")
        avg_hr = hr.get("averageHeartRate", 0) if isinstance(hr, dict) else 0
        vendor = stats.get("vendor", {})
        source = vendor.get("source", "Keep")
        device = vendor.get("deviceModel", "")
        vendor_display = f"{source} {device}".strip()

        try:
            # 向 Notion 添加数据
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "名称": {"title": [{"text": {"content": title}}]},
                    "日期": {"date": {"start": done_date}},
                    "时长": {"number": duration},
                    "距离": {"number": km},
                    "卡路里": {"number": stats.get("calorie")},
                    "类型": {"rich_text": [{"text": {"content": workout_id}}]},
                    "平均配速": {"number": pace_seconds},
                    "平均心率": {"number": avg_hr},
                    "天气": {"rich_text": [{"text": {"content": weather_info}}] if weather_info else []},
                    "数据来源": {"rich_text": [{"text": {"content": vendor_display}}]}
                }
            )
            print(f"\u2705 已同步: {done_date} - {title}")
        except Exception as e:
            print(f"\U0001f6ab 同步失败: {done_date} - {title}, 错误: {str(e)}")

print("\u2705 已完成所有 Notion 同步")
