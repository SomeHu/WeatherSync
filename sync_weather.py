import os
import requests
from notion_client import Client
from dotenv import load_dotenv
from datetime import datetime

# 加载环境变量
load_dotenv()

# 从环境变量获取配置信息
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY_ID = os.getenv("CITY_ID", "1798082")  # 默认城市：北京，城市 ID 可替换为你的城市 ID

# 检查环境变量
if not all([NOTION_TOKEN, NOTION_DATABASE_ID, OPENWEATHER_API_KEY]):
    print("缺少环境变量！请检查 NOTION_TOKEN, NOTION_DATABASE_ID 和 OPENWEATHER_API_KEY 是否设置。")
    exit(1)

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

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


# 创建页面
def create_weather_page():
    today = datetime.today().strftime('%Y-%m-%d')  # 获取今天的日期
    weather_info = get_weather(CITY_ID)
    
    # 创建页面标题
    title = f"🌤️ {today} 天气"
    
    try:
        # 向 Notion 添加数据
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "名称": {"title": [{"text": {"content": title}}]},
                "日期": {"date": {"start": today}},
                "天气": {"rich_text": [{"text": {"content": weather_info}}] if weather_info else []},
                "时长": {"number": 0},
                "距离": {"number": 0},
                "卡路里": {"number": 0},
                "类型": {"rich_text": [{"text": {"content": "天气同步"}}]},
                "平均配速": {"number": 0},
                "平均心率": {"number": 0},
                "数据来源": {"rich_text": [{"text": {"content": "手动同步"}}]}
            }
        )
        print(f"\u2705 已同步天气数据: {today} - {title}")
    except Exception as e:
        print(f"\U0001f6ab 同步失败: {today} - {title}, 错误: {str(e)}")

# 调用函数，创建天气页面
create_weather_page()
