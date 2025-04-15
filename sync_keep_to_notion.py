import os
import requests
from notion_client import Client
from dotenv import load_dotenv
import logging

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
notion = Client(auth=NOTION_TOKEN, log_level=logging.ERROR)

# Keep API 配置
LOGIN_API = "https://api.gotokeep.com/v1.1/users/login"
DATA_API = "https://api.gotokeep.com/pd/v3/stats/detail?dateUnit=all&type=&lastDate=0"
LOG_API = "https://api.gotokeep.com/pd/v3/{type}log/{id}"

keep_headers = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0",
    "Content-Type": "application/json",  # 修改为 application/json
}

def login_keep(mobile, password):
    print(f"登录 Keep - mobile: {mobile}, password: {password}")
    try:
        r = requests.post(
            LOGIN_API,
            headers=keep_headers,
            json={"mobile": mobile, "password": password}
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        token = data.get("token")
        if not token:
            print("登录失败：未获取到 Keep token。")
        keep_headers["Authorization"] = f"Bearer {token}"
        return token
    except Exception as e:
        print(f"登录 Keep 失败：{e}")
        print(f"响应内容：{r.text}")
        return None

def fetch_keep_data(token):
    try:
        r = requests.get(
            DATA_API,
            headers=keep_headers
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        records = data.get("records", [])
        print(f"获取到 {len(records)} 组运动记录")
        return records
    except Exception as e:
        print(f"获取 Keep 数据失败：{e}")
        return []

def get_run_data(log_type, log_id):
    try:
        r = requests.get(
            LOG_API.format(type=log_type, id=log_id),
            headers=keep_headers
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        return data
    except Exception as e:
        print(f"获取跑步数据详情失败 ({log_id})：{e}")
        return {}

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

def download_and_upload_cover(cover_url):
    try:
        resp = requests.get(cover_url, headers=keep_headers, stream=True)
        resp.raise_for_status()
        with open("temp_cover.jpg", "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print("图片下载成功：temp_cover.jpg")
        return cover_url  # 临时返回原 URL
    except Exception as e:
        print(f"处理封面图片失败：{e}")
        return ""

def create_notion_page(properties, cover_url=None):
    notion_page_data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties
    }
    if cover_url:
        if len(cover_url) > 2000:
            print(f"封面 URL 过长 ({len(cover_url)} 字符)，尝试下载并上传")
            cover_url = download_and_upload_cover(cover_url)
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

def process_workout_data(log):
    # 获取具体的运动数据
    workout_data = get_run_data(log["type"], log["id"])
    if workout_data:
        # 检查轨迹图 URL 是否有效
        track_url = workout_data.get("shareImg", "") or workout_data.get("trackWaterMark", "")
        if not track_url:
            track_url = "https://example.com/default_cover_image.jpg"  # 使用默认封面图
        # 插入到 Notion 中
        insert_workout_to_notion(workout_data, track_url)

def insert_workout_to_notion(workout_data, cover_url):
    # 准备插入 Notion 的数据
    properties = {
        "名称": {"title": [{"text": {"content": workout_data.get("name")}}]},
        "日期": {"date": {"start": workout_data.get("doneDate")}},
        "类型": {"rich_text": [{"text": {"content": workout_data.get("type")}}]},
        "时长": {"number": workout_data.get("duration")},
        "距离": {"number": workout_data.get("kmDistance")},
        "卡路里": {"number": workout_data.get("calorie")}
    }
    # 插入封面图
    notion_page_data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }
    if cover_url:
        notion_page_data["cover"] = {
            "type": "external",
            "external": {"url": cover_url}
        }
    notion.pages.create(**notion_page_data)

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
            print(f"\n处理记录：{done_date} - {sport_type} - {workout_id}")

            if page_exists(notion, NOTION_DATABASE_ID, done_date, workout_id):
                continue

            process_workout_data(item)  # 处理每一条运动记录

if __name__ == "__main__":
    main()
