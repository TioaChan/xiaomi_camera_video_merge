FROM python:3.9-slim
LABEL maintainer="8370450+TioaChan@users.noreply.github.com"

WORKDIR /app

ENV TZ=Asia/Shanghai
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV inputdir="/input"
ENV outputdir="/output"

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py entrypoint.sh /app/

VOLUME ["/input", "/output"]

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
