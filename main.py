from fastapi import FastAPI, HTTPException, Response, Request, WebSocket, WebSocketDisconnect
from daytona_sdk import Daytona, DaytonaConfig
import mimetypes
import re
import logging
import requests
import websockets
import asyncio
from config import settings
import docker

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

@app.api_route("/{file_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
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
        
        # 获取沙箱的IP地址
        ip_address = get_container_internal_ip(sandbox.id)
        logger.info(f"沙箱 {sandbox.id} 的IP地址为: {ip_address}")
        
        
        
        info = sandbox.info()
        logger.info(f"沙箱信息: {info}")
        if info.public == False:
            logger.error(f"沙箱 {sandbox.id} 未开放")
            raise HTTPException(status_code=404, detail="Sandbox not public")
        
        url = f"http://{ip_address}:{port}/{file_path}"
        ##转发这个请求到沙箱
        print(f"转发请求到沙箱: {url}")

        req_content = await request.body()
        resp = requests.request(
            method=request.method,
            url=url,
            headers={key: value for key, value in request.headers.items() if key.lower() != 'host'},
            data=req_content,
            cookies=request.cookies,
            allow_redirects=False)
    
        # 返回响应给客户端
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = {name: value for name, value in resp.headers.items() if name.lower() not in excluded_headers}
    
        return Response(content=resp.content, status_code=resp.status_code, headers=headers)
        
    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"File not found or error accessing file: {str(e)}")
    



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket连接转发到沙箱。
    支持WebSocket协议的转发。
    """
    try:
        # 获取请求URL
        full_url = str(websocket.url)
        logger.info(f"收到WebSocket连接请求: {full_url}")
        
        # 解析URL中的特定字段
        url_pattern = r'(?:http|ws)(?:s)?://([^-]+)-([^.]+)\.(.+?)(?:/ws)?'
        match = re.search(url_pattern, full_url)
        logger.debug(f"尝试匹配URL: {full_url}, 使用模式: {url_pattern}")
        
        if match:
            port = match.group(1)
            workspace_id = match.group(2)
            domain = match.group(3)
            logger.debug(f"WebSocket URL解析结果 - Port: {port}, Workspace ID: {workspace_id}, Domain: {domain}")
        else:
            logger.error(f"无效的WebSocket URL格式: {full_url}")
            await websocket.close(code=1008, reason="无效的URL格式")
            return
        
        # 查找沙箱
        sandbox = daytona.find_one(sandbox_id=workspace_id)
        if not sandbox:
            logger.error(f"未找到沙箱: {workspace_id}")
            await websocket.close(code=1008, reason="沙箱不存在")
            return
        
        # 获取沙箱的IP地址
        ip_address = get_container_internal_ip(sandbox.id)
        logger.info(f"沙箱 {sandbox.id} 的IP地址为: {ip_address}")
        
        info = sandbox.info()
        logger.info(f"沙箱信息: {info}")
        if info.public == False:
            logger.error(f"沙箱 {sandbox.id} 未开放")
            await websocket.close(code=1008, reason="沙箱未开放访问")
            return
        
        # WebSocket连接目标URL
        target_ws_url = f"ws://{ip_address}:{port}/ws"
        logger.info(f"转发WebSocket连接到: {target_ws_url}")
        
        # 接受WebSocket连接
        await websocket.accept()
        
        # 发送初始握手信息
        try:
            await websocket.send_text('{"type":"connection_established","status":"connected"}')
        except Exception as e:
            logger.error(f"发送初始握手信息失败: {str(e)}")
            
        # 使用websockets库与目标服务器建立连接
        max_retries = 3
        retry_count = 0
        connection_successful = False
        ws_client = None
        
        while retry_count < max_retries and not connection_successful:
            try:
                logger.info(f"尝试连接到目标服务器 (尝试 {retry_count+1}/{max_retries}): {target_ws_url}")
                
                # 增加连接超时时间和重试机制
                ws_client = await websockets.connect(
                    target_ws_url,
                    ping_interval=20,  # 每20秒ping一次
                    ping_timeout=30,   # ping超时时间30秒
                    close_timeout=10   # 关闭超时10秒
                )
                connection_successful = True
                logger.info(f"成功连接到目标WebSocket服务器: {target_ws_url}")
                break
            except Exception as e:
                logger.error(f"连接目标WebSocket服务器失败: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 1 * retry_count  # 逐渐增加等待时间
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
        
        if not connection_successful:
            logger.error(f"无法连接到目标WebSocket服务器，已达到最大重试次数")
            await websocket.close(code=1013, reason="无法连接到目标服务器")
            return
                
        # 如果成功连接，处理WebSocket通信
        try:
            async with ws_client as ws_connection:
                # 定义从客户端到目标服务器的转发函数
                async def forward_to_target():
                    try:
                        while True:
                            try:
                                # 尝试接收消息，可能是文本或二进制
                                message = await websocket.receive()
                                
                                # 根据消息类型处理
                                if message["type"] == "websocket.receive":
                                    if "text" in message:
                                        text_data = message["text"]
                                        # 处理文本消息（即使是空字符串或"N/A"也要转发）
                                        if text_data == "N/A":
                                            logger.debug("接收到特殊标记 'N/A'，正常转发")
                                        await ws_connection.send(text_data)
                                        logger.debug(f"转发文本消息到目标服务器: '{text_data[:50]}{'...' if len(text_data) > 50 else ''}'")
                                    elif "bytes" in message:
                                        # 处理二进制消息
                                        binary_data = message["bytes"]
                                        if binary_data:
                                            await ws_connection.send(binary_data)
                                            logger.debug(f"转发二进制消息到目标服务器，大小: {len(binary_data)} 字节")
                                        else:
                                            # 处理空二进制数据
                                            await ws_connection.send(b"")
                                            logger.debug("转发空二进制消息到目标服务器")
                                elif message["type"] == "websocket.disconnect":
                                    logger.info("收到WebSocket断开连接消息")
                                    return
                            except WebSocketDisconnect:
                                logger.info("客户端WebSocket连接已断开")
                                return
                            except Exception as e:
                                logger.error(f"接收/转发消息时出错: {str(e)}")
                                return
                    except Exception as e:
                        logger.error(f"转发消息到目标服务器时出错: {str(e)}")
                        return
                
                # 定义从目标服务器到客户端的转发函数
                async def forward_to_client():
                    try:
                        while True:
                            try:
                                # 从目标服务器接收消息
                                data = await ws_connection.recv()
                                
                                # 转发到客户端，并根据数据类型使用适当的方法
                                if isinstance(data, str):
                                    # 文本消息
                                    text_data = data
                                    if text_data == "N/A":
                                        logger.debug("从服务器收到特殊标记 'N/A'，正常转发")
                                    await websocket.send_text(text_data)
                                    logger.debug(f"转发文本消息到客户端: '{text_data[:50]}{'...' if len(text_data) > 50 else ''}'")
                                elif isinstance(data, bytes):
                                    # 二进制消息
                                    binary_data = data
                                    if binary_data:
                                        await websocket.send_bytes(binary_data)
                                        logger.debug(f"转发二进制消息到客户端，大小: {len(binary_data)} 字节")
                                    else:
                                        # 处理空二进制数据
                                        await websocket.send_bytes(b"")
                                        logger.debug("转发空二进制消息到客户端")
                                elif data is None:
                                    # None 值通常表示某种特殊情况
                                    logger.debug("从服务器收到 None 值，转发为空字符串")
                                    await websocket.send_text("")
                                else:
                                    # 其他类型（不太可能出现，但为了健壮性）
                                    logger.warning(f"收到未知类型的消息: {type(data)}")
                                    try:
                                        string_data = str(data)
                                        await websocket.send_text(string_data)
                                        logger.debug(f"将未知类型消息转换为字符串并发送: {string_data[:50]}...")
                                    except Exception as e:
                                        logger.error(f"转换未知类型消息时出错: {str(e)}")
                                        await websocket.send_text("CONVERSION_ERROR")
                            except websockets.exceptions.ConnectionClosed as e:
                                logger.info(f"与目标服务器的WebSocket连接已关闭: {e.code} {e.reason}")
                                return
                            except Exception as e:
                                logger.error(f"从目标服务器接收/转发消息时出错: {str(e)}")
                                return
                    except Exception as e:
                        logger.error(f"转发消息到客户端时出错: {str(e)}")
                        return
                
                # 添加保活机制
                async def keep_alive():
                    try:
                        while True:
                            # 每30秒发送一次心跳包
                            await asyncio.sleep(30)
                            if websocket.client_state.name == "CONNECTED":
                                logger.debug("发送WebSocket保活心跳")
                                try:
                                    # 尝试向客户端发送心跳（可能不是所有客户端都支持）
                                    await websocket.send_text('{"type":"ping"}')
                                except Exception as e:
                                    logger.debug(f"发送保活心跳失败: {str(e)}")
                                    break
                            else:
                                logger.debug("客户端已断开，停止保活")
                                break
                    except Exception as e:
                        logger.error(f"保活过程中发生错误: {str(e)}")
                        return
                
                logger.info("开始WebSocket双向转发...")
                
                # 同时运行三个任务: 客户端到服务器，服务器到客户端，以及保活
                forward_client_task = asyncio.create_task(forward_to_client())
                forward_target_task = asyncio.create_task(forward_to_target())
                keep_alive_task = asyncio.create_task(keep_alive())
                
                # 等待任意一个任务完成（通常是因为连接断开）
                done, pending = await asyncio.wait(
                    [forward_client_task, forward_target_task, keep_alive_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 取消剩余任务
                for task in pending:
                    task.cancel()
                    
                # 等待取消的任务完成
                try:
                    await asyncio.gather(*pending, return_exceptions=True)
                except:
                    pass
                
                logger.info("WebSocket连接转发已结束")
                
        except Exception as e:
            logger.error(f"处理WebSocket通信过程中发生错误: {str(e)}")
            try:
                await websocket.close(code=1011, reason="处理通信时出错")
            except:
                pass
            
        logger.info("====== WebSocket连接转发完成 ======")
    except Exception as e:
        logger.error(f"处理WebSocket连接时发生错误: {str(e)}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=f"内部服务器错误: {str(e)}")
        except:
            pass


def get_container_internal_ip(container_name_or_id):
    # 创建一个Docker客户端
    client = docker.from_env()

    try:
        # 获取容器对象
        container = client.containers.get(container_name_or_id)
        
        # 获取容器的网络设置
        container_network_settings = container.attrs['NetworkSettings']['Networks']
        
        # 假设只连接到一个网络，取出第一个（且通常是唯一的）网络的IP地址
        for network_name, network_info in container_network_settings.items():
            ip_address = network_info['IPAddress']
            print(f"容器 {container_name_or_id} 在网络 {network_name} 上的 IP 地址为: {ip_address}")
            return ip_address
            
    except docker.errors.NotFound:
        print("未找到指定的容器")
    except Exception as e:
        print(f"发生错误: {e}")