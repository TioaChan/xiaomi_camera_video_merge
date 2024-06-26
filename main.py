import argparse
import os
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from loguru import logger

parser = argparse.ArgumentParser(description='合并米家摄像头视频，以天为单位。')
parser.add_argument('indir', help='原米家摄像头视频目录。')
parser.add_argument('--outdir', default='./', help='合并后视频存放目录，目录不存在会被创建。默认当前目录。')
args = parser.parse_args()


def merge_videos(vidlist_file: Path, target_file: Path):
    """执行 ffmpeg 命令合并视频。"""
    # 需要对音频重新编码，否则会报错：
    # Could not find tag for codec pcm_alaw in stream #1, codec not currently supported in container when concatenating 2 files using ffmpeg
    # ffmpeg -y overwrite
    if platform.system().lower() == "windows":
        cmd = f"ffmpeg -loglevel quiet -f concat -safe 0 -i {vidlist_file} -c:v copy -c:a flac -strict -2 {target_file}"
        subprocess.run(cmd)
    else:
        cmd = f"ffmpeg -loglevel quiet -y -f concat -safe 0 -i {vidlist_file} -c:v copy -c:a aac -strict -2 {target_file}"
        subprocess.run(cmd, shell=True)

    with open(vidlist_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            video_path = line.strip().replace("file ", "")
            parent_path = Path(video_path).parent
            if parent_path.exists():
                logger.info(f"{parent_path} will be removed.")
                shutil.rmtree(parent_path, ignore_errors=True)
    f.close()
    logger.info(f"{vidlist_file} will be removed.")
    os.remove(vidlist_file)


def has_subdirectories(directory):
    subdirectories = [item for item in os.listdir(directory) if os.path.isdir(os.path.join(directory, item))]
    return bool(subdirectories)


def merge_dirs(in_dir: Path, output_dir: Path, date_name: str, parent_path: str):
    """合并目录下的监控文件，在当前目录生成以天为单位的视频。
    indir 结构：
    indir
        2021051001
        2021051002
        2021051003
        ...
    即，子目录结构为：年月日时。
    """
    if not Path(output_dir).exists():
        logger.info(f'{output_dir} 不存在，即将被创建')
        Path(output_dir).mkdir(parents=True)

    date_dict = {}

    current_date = datetime.now().strftime('%Y%m%d')
    date_dict[current_date] = []

    if Path(in_dir).is_file():
        logger.error(f"{in_dir} is not a directory.")
        return
    # 小米第一代文件目录有多层
    for d in Path(in_dir).iterdir():
        if d.is_file() and d.name != '.DS_Store' and d.name != '@eaDir':
            # 兼容一级目录是视频文件
            date_dict[date_name] = [Path(in_dir)]
            break
        if not d.is_dir():
            continue
        date = d.stem[:8]
        if date not in date_dict:
            date_dict[date] = []
        date_dict[date].append(d)

    if current_date in date_dict:
        date_dict.pop(current_date)

    for ds_date, ds in date_dict.items():
        videos = []
        for d in ds:
            mp4_list = list(Path(d).glob("*.mp4"))
            videos.extend(mp4_list)

        # print("data_dict:", d, has_subdirectories(Path(d)))
        logger.info(f"date_dict:{d}, {has_subdirectories(Path(d))}")

        if len(videos) == 0 and Path(d).is_dir() and has_subdirectories(Path(d)):
            # 往下层递归
            merge_dirs(Path(d), output_dir, date_name, ds_date)
        logger.info(f"{ds_date}, {len(videos)} videos")
        if not videos:
            continue
        videos = sorted(videos, key=lambda f: int(f.stem.split("_")[-1]))
        videos = ["file " + str(f.resolve(strict=True)).replace("\\", "/") for f in videos]

        merge_output_dir = f'{output_dir}/{date_name}/{parent_path}'
        if not Path(merge_output_dir).exists():
            Path(merge_output_dir).mkdir(parents=True)

        video_list_path = f"{merge_output_dir}/{ds_date}_video_list.txt"

        Path(video_list_path).write_text("\n".join(videos), encoding="utf8")
        merge_videos(Path(video_list_path), Path(merge_output_dir).joinpath(f"{ds_date}.mp4"))


def startup(input_dir: str, output_dir: str):
    for item in Path(input_dir).iterdir():
        if item.name != '.DS_Store' and item.name != '@eaDir':
            logger.info(f"start merge {item.name} video")
            merge_dirs(Path(item), Path(output_dir), item.name, "")


if __name__ == "__main__":
    logger.info(f"current time {datetime.now()},source dir : {args.indir}, target dir: {args.outdir}")
    startup(args.indir, args.outdir)
