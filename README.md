### 服务器部署步骤

1. 进入项目目录：
   ```bash
   cd /data/daytonamy
   ```

2. 激活conda环境：
   ```bash
   conda activate daytonamy
   ```

3. 使用gunicorn启动应用：
   ```bash
   nohup gunicorn -c gunicorn_config.py main:app 2>&1 &
   ```

### 服务器信息

- **IP地址**: 125.76.110.88
- **端口**: 8000
