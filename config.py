import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Settings:
    # FastAPI 应用配置
    APP_NAME = "Daytona File Service"
    APP_VERSION = "1.0.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Daytona配置
    DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
    DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "http://127.0.0.1:3000/api")
    
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    WORKERS = int(os.getenv("WORKERS", "4"))  # Gunicorn worker数量
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "app.log")

settings = Settings() 