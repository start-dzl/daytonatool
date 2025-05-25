### 服务器部署步骤


1. 使用gunicorn启动应用：
   ```bash
   nohup gunicorn -c gunicorn_config.py main:app 2>&1 &
   ```
## 解决 Daytona 本地部署沙盒访问问题的思路

在本地化部署 Daytona 时，我们使用的是 Docker 镜像。遇到沙盒无法访问的问题（详情参见 [Daytona Issue #1861](https://github.com/daytonaio/daytona/issues/1861）），可以通过编写一个转发请求到 Docker 容器接口的方法作为临时解决方案。

### 解决步骤如下：

1. **确认 Docker 环境**：确保 Daytona 已通过 Docker 成功部署在本地环境中。
2. **编写转发服务**：开发一个简单的转发服务，用于将对沙盒的请求转发至正确的 Docker 容器接口上。
3. **部署转发服务**：将此转发服务与 Daytona 一起部署在同一网络环境下，确保其能够正确地与 Daytona 的 Docker 容器通信。
4. **修改沙盒的domain**：Daytona 数据库 node 表，domain 修改指向 转发服务

通过这种方式，可以在官方修复该问题之前提供一个可行的临时解决方案。请持续关注 Daytona 官方更新，并在合适的时候替换为官方修复版本。
