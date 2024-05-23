# 使用官方的 Python 基础镜像
FROM python:3.9-slim

# 维护者信息
LABEL maintainer="8370450+TioaChan@users.noreply.github.com"

# 设置工作目录
WORKDIR /app

# 安装 ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 复制当前目录内容到工作目录
COPY . /app

# 安装 Python 依赖包
RUN pip install --no-cache-dir -r requirements.txt

# 设置容器启动时运行的命令
CMD ["python", "main.py"]
