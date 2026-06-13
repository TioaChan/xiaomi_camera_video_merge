# xiaomi_camera_video_merge

按天合并米家摄像头录制的 `mp4` 片段。默认只合并当天录像，默认保留原始视频片段。

## 目录结构

传入目录必须是实际录像目录，即该目录下直接包含 `YYYYMMDDHH` 形式的小时目录：

```text
xiaomi_camera_videos
  2026061307
  2026061308
  2026061309
```

程序只处理传入目录本身，不会自动进入摄像头 SN 子目录。如果你的目录结构是：

```text
xiaomi_camera_videos
  <camera-sn>
    2026061307
    2026061308
```

请把 `xiaomi_camera_videos/<camera-sn>` 作为输入目录。

## Docker 运行

```shell
docker run --rm -it \
  -v /your/xiaomi_camera_videos/<camera-sn>:/input \
  -v /your/output:/output \
  tioatyan/xiaomi_camera_video_merge:latest
```

合并成功后删除原始片段：

```shell
docker run --rm -it \
  -v /your/xiaomi_camera_videos/<camera-sn>:/input \
  -v /your/output:/output \
  tioatyan/xiaomi_camera_video_merge:latest \
  --delete-source
```

## 本地运行

```shell
pip install -r requirements.txt
python main.py --outdir /your/output /your/xiaomi_camera_videos/<camera-sn>
```

常用参数：

- `--delete-source`：合并成功后删除原始视频片段目录。
- `--date YYYYMMDD`：合并指定日期。默认当天。
- `--ffmpeg /path/to/ffmpeg`：指定 `ffmpeg` 路径。
