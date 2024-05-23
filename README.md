### 运行
```shell
docker run --pull=always --rm -it \
-v /source:/app/indir \
-v /target:/outdir \
-e inputdir=/app/indir -e outputdir=/outdir \
tioatyan/xiaomi_camera_video_merge:latest
```