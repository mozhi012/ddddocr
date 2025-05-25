FROM python:3.9-slim

# 设置环境变量，确保 Python 输出不被缓冲，方便 Docker 日志查看
ENV PYTHONUNBUFFERED=1

# 创建并设置工作目录
WORKDIR /app

# 复制依赖定义文件到工作目录
COPY requirements.txt .

# 安装 Python 依赖
# 注意: 这里使用 pip。如果需要 cnpm，通常是在 Node.js 环境或特定的国内镜像配置中使用。
# 对于 Python 的 Docker 镜像，标准做法是使用 pip。
# 如果 ddddocr 依赖了需要编译的库，可能需要安装额外的系统依赖 (如 build-essential, gcc 等)
# 但 ddddocr 官方文档表示尽量减少依赖，我们先尝试直接安装。
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码和 HTML 测试页面到工作目录
COPY app.py .
COPY examples.html .

# 暴露应用运行的端口 (与 app.py 中的 Flask 运行端口一致)
EXPOSE 5000

# 定义容器启动时运行的命令
# 使用 gunicorn 作为 WSGI 服务器来运行 Flask 应用
# --workers: gunicorn worker 进程的数量，通常建议为 (2 * CPU核心数) + 1
# --bind: 绑定的 IP 和端口。0.0.0.0 表示监听所有网络接口。
# app:app: 指向 app.py 文件中的 app Flask 实例
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "app:app"] 