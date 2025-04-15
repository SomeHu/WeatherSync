import os
import requests
from notion_client import Client
from dotenv import load_dotenv
from urllib.parse import quote

# 加载环境变量
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
KEEP_MOBILE = os.getenv("KEEP_MOBILE")
KEEP_PASSWORD = os.getenv("KEEP_PASSWORD")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY_ID = os.getenv("CITY_ID", "1798082")
AMAP_KEY = os.getenv("AMAP_KEY")

# 校验环境变量
if not all([NOTION_TOKEN, NOTION_DATABASE_ID, KEEP_MOBILE, KEEP_PASSWORD, OPENWEATHER_API_KEY]):
    print("缺少关键环境变量，请检查 NOTION_TOKEN、NOTION_DATABASE_ID、KEEP_MOBILE、KEEP_PASSWORD、OPENWEATHER_API_KEY 是否设置。")
    exit(1)

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

def login_keep(mobile, password):
    r = requests.post(
        "https://api.gotokeep.com/v1.1/users/login",
        json={"mobile": mobile, "password": password}
    )
    r.raise_for_status()
    data = r.json().get("data", {})
    return data.get("token")

def fetch_keep_data(token):
    r = requests.get(
        "https://api.gotokeep.com/pd/v3/stats/detail",
        params={"dateUnit": "all", "type": "", "lastDate": 0},
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("records", [])

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
    except:
        return "无法获取天气信息"

def page_exists(notion_client, database_id, date_str, workout_id):
    query_res = notion_client.databases.query(
        database_id=database_id,
        filter={
            "and": [
                {"property": "日期", "date": {"equals": date_str}},
                {"property": "类型", "rich_text": {"contains": workout_id}}
            ]
        }
    )
    return len(query_res.get("results", [])) > 0

def create_notion_page(properties, cover_url=None):
    notion_page_data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties
    }
    if cover_url:
        notion_page_data["cover"] = {
            "type": "external",
            "external": {"url": cover_url}
        }
    return notion.pages.create(**notion_page_data)

def append_image_block(page_id, image_url):
    notion.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": image_url}
                }
            }
        ]
    )

def generate_run_map_url(coords):
    if not AMAP_KEY or not coords:
        return ""
    point_list = []
    for (lat, lng) in coords:
        point_list.append(f"{lng},{lat}")
    path_str = ";".join(point_list)
    base_url = "https://restapi.amap.com/v3/staticmap"
    params = {
        "key": AMAP_KEY,
        "size": "1024*512",
        "paths": f"2,0xFF0000,1,,:{path_str}"
    }
    req = requests.Request("GET", base_url, params=params).prepare()
    return req.url

def main():
    token = login_keep(KEEP_MOBILE, KEEP_PASSWORD)
    if not token:
        print("获取 Keep token 失败，请确认 Keep 账号密码是否正确。")
        return

    records = fetch_keep_data(token)
    print(f"共获取到 {len(records)} 组运动记录")

    for group in records:
        logs = group.get("logs", [])
        for item in logs:
            stats = item.get("stats") or {}
            if not stats:
                continue

            done_date = stats.get("doneDate", "")
            workout_id = stats.get("id", "")
            sport_type = stats.get("type", "").lower()
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

            gps_points = stats.get("gpsData", [])
            coords = [(p.get("lat"), p.get("lng")) for p in gps_points if p.get("lat") and p.get("lng")]

            track_url = ""
            if sport_type in ["running", "jogging"] and coords:
                track_url = generate_run_map_url(coords)

            # 假设步行活动可能有其他可视化图（需确认 Keep API 实际字段）
            chart_url = stats.get("stepFreqChart", "")  # 替换为实际字段名，如有
            cover_url = track_url if track_url else chart_url if sport_type == "walking" else ""

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

            try:
                new_page = create_notion_page(props, cover_url=cover_url)
                print(f"已创建页面: {done_date} - {title}")
            except Exception as e:
                print(f"创建页面失败: {done_date} - {title} -> {e}")
                continue

            page_id = new_page["id"]

            # 可选：如果需要图片同时出现在页面内容中，取消注释
            # if cover_url:
            #     try:
            #         append_image_block(page_id, cover_url)
            #         print(f"已插入图片到页面内容: {'轨迹图' if track_url else '步频图'}")
            #     except Exception as e:
            #         print(f"插入图片失败: {e}")

if __name__ == "__main__":
    main()
