from fastapi import FastAPI, HTTPException, Response, Request
from daytona_sdk import Daytona, DaytonaConfig
import mimetypes
import re
import logging
from config import settings

# 配置日志
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# 初始化 Daytona 客户端
config = DaytonaConfig(
    api_key=settings.DAYTONA_API_KEY,
    api_url=settings.DAYTONA_API_URL
)
daytona = Daytona(config)

@app.get("/{file_path:path}")
async def download_file(file_path: str, request: Request):
    """
    从沙箱下载指定路径的文件，并在线打开（非强制下载）。
    文件路径直接从URL中获取。
    """
    try:
        # 获取完整URL
        full_url = str(request.url)
        logger.info(f"收到文件请求: {full_url}")
        
        # 解析URL中的特定字段
        url_pattern = r'http://(\d+)-([^.]+)\.(.+?)/'
        match = re.search(url_pattern, full_url)
        
        if match:
            port = match.group(1)
            workspace_id = match.group(2)
            domain = match.group(3)
            logger.debug(f"URL解析结果 - Port: {port}, Workspace ID: {workspace_id}, Domain: {domain}")
        else:
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        # 查找沙箱
        sandbox = daytona.find_one(sandbox_id=workspace_id)
        if not sandbox:
            logger.error(f"未找到沙箱: {workspace_id}")
            raise HTTPException(status_code=404, detail="Sandbox not found")
        
        # 如果文件路径为空，设置默认值为 index.html
        if not file_path:
            file_path = "index.html"
            logger.debug("使用默认文件路径: index.html")

        # 构建完整的文件路径
        remote_file_path = f"/workspace/{file_path}"
        logger.debug(f"访问文件路径: {remote_file_path}")

        # 下载文件内容
        content = sandbox.fs.download_file(remote_file_path)
        
        # 根据文件扩展名自动判断 MIME 类型
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        logger.info(f"文件 {file_path} 下载成功")
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"inline; filename={file_path.split('/')[-1]}"
            }
        )
    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"File not found or error accessing file: {str(e)}")