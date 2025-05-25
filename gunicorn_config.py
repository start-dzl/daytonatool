from config import settings

# 服务器套接字
bind = f"{settings.HOST}:{settings.PORT}"
workers = settings.WORKERS

# 工作模式
worker_class = "uvicorn.workers.UvicornWorker"

# 日志配置
accesslog = "access.log"
errorlog = "error.log"
loglevel = settings.LOG_LEVEL.lower()

# 进程名称
proc_name = "daytona_file_service"

# 超时设置
timeout = 120
keepalive = 5

# 重启策略
max_requests = 1000
max_requests_jitter = 50

# 调试选项
reload = settings.DEBUG
reload_engine = "auto" 