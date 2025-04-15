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
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY_ID = os.getenv("CITY_ID", "1798082")

# 校验环境变量
if not all([NOTION_TOKEN, NOTION_DATABASE_ID, KEEP_MOBILE, KEEP_PASSWORD, OPENWEATHER_API_KEY]):
    print("缺少关键环境变量，请检查 NOTION_TOKEN、NOTION_DATABASE_ID、KEEP_MOBILE、KEEP_PASSWORD、OPENWEATHER_API_KEY 是否设置。")
    exit(1)

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

def login_keep(mobile, password):
    try:
        r = requests.post(
            "https://api.gotokeep.com/v1.1/users/login",
            json={"mobile": mobile, "password": password}
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        token = data.get("token")
        if not token:
            print("登录失败：未获取到 Keep token。")
        return token
    except Exception as e:
        print(f"登录 Keep 失败：{e}")
        return None

def fetch_keep_data(token):
    try:
        r = requests.get(
            "https://api.gotokeep.com/pd/v3/stats/detail",
            params={"dateUnit": "all", "type": "", "lastDate": 0},
            headers={"Authorization": f"Bearer {token}"}
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        records = data.get("records", [])
        print(f"获取到 {len(records)} 组运动记录")
        return records
    except Exception as e:
        print(f"获取 Keep 数据失败：{e}")
        return []

def get_weather(city_id, api_key):
    url = f"http://api.openweathermap.org/data/2.5/weather?id={city_id}&appid={api_key}&units=metric&lang=zh_cn"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        wdata = resp.json()
        if wdata.get("cod") == 200:
            desc = wdata["weather"][0]["description"]
            temp = wdata["main"]["temp"]
            return f"{desc} ~ {temp}°C"
        return f"天气请求失败: {wdata.get('message','未知错误')}"
    except Exception as e:
        print(f"获取天气信息失败：{e}")
        return "无法获取天气信息"

def page_exists(notion_client, database_id, date_str, workout_id):
    try:
        query_res = notion_client.databases.query(
            database_id=database_id,
            filter={
                "and": [
                    {"property": "日期", "date": {"equals": date_str}},
                    {"property": "类型", "rich_text": {"contains": workout_id}}
                ]
            }
        )
        exists = len(query_res.get("results", [])) > 0
        if exists:
            print(f"页面已存在：{date_str} - {workout_id}")
        return exists
    except Exception as e:
        print(f"检查页面存在失败：{e}")
        return False

def create_notion_page(properties, cover_url=None):
    notion_page_data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties
    }
    if cover_url:
        print(f"设置封面 URL：{cover_url}")
        notion_page_data["cover"] = {
            "type": "external",
            "external": {"url": cover_url}
        }
    try:
        page = notion.pages.create(**notion_page_data)
        print("页面创建成功")
        return page
    except Exception as e:
        print(f"创建 Notion 页面失败：{e}")
        return None

def main():
    token = login_keep(KEEP_MOBILE, KEEP_PASSWORD)
    if not token:
        return

    records = fetch_keep_data(token)
    if not records:
        return

    for group in records:
        logs = group.get("logs", [])
        for item in logs:
            stats = item.get("stats") or {}
            if not stats:
                print("跳过：无 stats 数据")
                continue

            done_date = stats.get("doneDate", "")
            workout_id = stats.get("id", "")
            sport_type = stats.get("type", "").lower()
            print(f"处理记录：{done_date} - {sport_type} - {workout_id}")

            if page_exists(notion, NOTION_DATABASE_ID, done_date, workout_id):
                continue

            km = stats.get("kmDistance", 0.0)
            duration = stats.get("duration", 0)
            calorie = stats.get("calorie", 0)
            name = stats.get("name", "未命名")
            name_suffix = stats.get("nameSuffix", "")
            heart_rate_data = stats.get("heartRate", {})
            avg_hr = heart_rate_data.get("averageHeartRate", 0) if isinstance(heart_rate_data, dict) else 0

            weather_info = get_weather(CITY_ID, OPENWEATHER_API_KEY)
            pace_seconds = int(duration / km) if km > 0 else 0
            vendor = stats.get("vendor", {})
            source = vendor.get("source") or ""
            device_model = vendor.get("deviceModel") or ""
            vendor_str = f"{source} {device_model}".strip()
            title = f"🏃‍♂️ {name} {name_suffix}"

            # 获取 Keep 自带的轨迹图 URL（字段名需确认）
            track_url = stats.get("mapUrl", "")  # 替换为实际字段名
            if sport_type in ["running", "jogging"]:
                if track_url:
                    print(f"找到轨迹图 URL：{track_url}")
                    # 验证 URL 是否有效
                    try:
                        resp = requests.head(track_url, timeout=5)
                        if resp.status_code != 200:
                            print(f"轨迹图 URL 无效，状态码：{resp.status_code}")
                            track_url = ""
                    except Exception as e:
                        print(f"验证轨迹图 URL 失败：{e}")
                        track_url = ""
                else:
                    print("未找到轨迹图 URL")
            else:
                print(f"跳过轨迹图：运动类型为 {sport_type}")
                track_url = ""

            # 步频图（占位，需确认字段）
            chart_url = stats.get("stepFreqChart", "") if sport_type == "walking" else ""
            cover_url = track_url or chart_url

            props = {
                "名称": {"title": [{"text": {"content": title}}]},
                "日期": {"date": {"start": done_date}},
                "时长": {"number": duration},
                "距离": {"number": km},
                "卡路里": {"number": calorie},
                "类型": {"rich_text": [{"text": {"content": workout_id}}]},
                "平均配速": {"number": pace_seconds},
                "平均心率": {"number": avg_hr},
                "天气": {"rich_text": [{"text": {"content": weather_info}}]},
                "数据来源": {"rich_text": [{"text": {"content": vendor_str}}]}
            }

            if track_url:
                props["轨迹图"] = {"url": track_url}

            new_page = create_notion_page(props, cover_url=cover_url)
            if new_page:
                print(f"成功创建页面：{done_date} - {title}")
            else:
                print(f"页面创建失败：{done_date} - {title}")

if __name__ == "__main__":
    main()
