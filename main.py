import argparse
import platform
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from loguru import logger


IGNORED_NAMES = {".DS_Store", "@eaDir"}
VIDEO_SUFFIX = ".mp4"
DATE_FORMAT = "%Y%m%d"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="合并米家摄像头视频，以天为单位。")
    parser.add_argument("indir", help="原米家摄像头视频目录。")
    parser.add_argument(
        "--outdir",
        default="./",
        help="合并后视频存放目录，目录不存在会被创建。默认当前目录。",
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="合并成功后删除原始视频片段目录。默认保留源文件。",
    )
    parser.add_argument(
        "--date",
        type=validate_date,
        help="要合并的日期，格式 YYYYMMDD。默认当天。",
    )
    parser.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="ffmpeg 可执行文件路径。默认使用 PATH 中的 ffmpeg。",
    )
    return parser.parse_args(argv)


def is_ignored(path: Path) -> bool:
    return path.name in IGNORED_NAMES


def natural_sort_key(path: Path) -> Tuple[Tuple[int, object], ...]:
    parts = re.split(r"(\d+)", path.stem)
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower()) for part in parts)


def iter_mp4_files(directory: Path) -> List[Path]:
    videos = (
        child
        for child in directory.iterdir()
        if child.is_file() and child.suffix.lower() == VIDEO_SUFFIX and not is_ignored(child)
    )
    return sorted(videos, key=natural_sort_key)


def today() -> str:
    return datetime.now().strftime(DATE_FORMAT)


def validate_date(value: str) -> str:
    try:
        datetime.strptime(value, DATE_FORMAT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYYMMDD format") from exc
    return value


def collect_videos_for_date(in_dir: Path, target_date: str) -> List[Path]:
    """收集传入目录下目标日期的录像片段，不递归进入其它业务子目录。"""
    video_dirs = []

    if in_dir.name.startswith(target_date):
        video_dirs.append(in_dir)

    for child in sorted(in_dir.glob(f"{target_date}*"), key=lambda item: item.name):
        if is_ignored(child):
            continue
        if child.is_dir():
            video_dirs.append(child)

    videos = []
    for video_dir in dict.fromkeys(video_dirs):
        videos.extend(iter_mp4_files(video_dir))

    return sorted(videos, key=lambda video: (video.parent.name, natural_sort_key(video)))


def format_concat_line(video: Path) -> str:
    path = video.resolve(strict=True).as_posix()
    return "file '" + path.replace("'", "'\\''") + "'"


def write_video_list(video_list_path: Path, videos: Sequence[Path]) -> None:
    video_list_path.write_text(
        "\n".join(format_concat_line(video) for video in videos) + "\n",
        encoding="utf8",
    )


def audio_codec() -> str:
    return "flac" if platform.system().lower() == "windows" else "aac"


def build_ffmpeg_command(ffmpeg_bin: str, vidlist_file: Path, target_file: Path) -> List[str]:
    return [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(vidlist_file),
        "-c:v",
        "copy",
        "-c:a",
        audio_codec(),
        "-strict",
        "-2",
        str(target_file),
    ]


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def remove_source_dirs(source_dirs: Iterable[Path], target_file: Path) -> None:
    resolved_target = target_file.resolve()
    resolved_dirs = {source_dir.resolve() for source_dir in source_dirs}

    for source_dir in sorted(resolved_dirs, key=lambda path: len(path.parts), reverse=True):
        if not source_dir.exists():
            continue
        if is_relative_to(resolved_target, source_dir):
            logger.warning(
                f"skip remove {source_dir}, because it contains target file {target_file}"
            )
            continue

        logger.info(f"{source_dir} will be removed.")
        try:
            shutil.rmtree(source_dir)
        except OSError as exc:
            logger.warning(f"failed to remove {source_dir}: {exc}")


def merge_videos(
    vidlist_file: Path,
    target_file: Path,
    source_dirs: Optional[Iterable[Path]] = None,
    remove_source: bool = False,
    ffmpeg_bin: str = "ffmpeg",
) -> None:
    """执行 ffmpeg 命令合并视频。"""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_ffmpeg_command(ffmpeg_bin, vidlist_file, target_file)

    logger.info(f"merge {vidlist_file} -> {target_file}")
    subprocess.run(cmd, check=True)

    if remove_source and source_dirs is not None:
        remove_source_dirs(source_dirs, target_file)

    logger.info(f"{vidlist_file} will be removed.")
    vidlist_file.unlink(missing_ok=True)


def merge_dirs(
    in_dir: Path,
    output_dir: Path,
    date_name: str,
    target_date: str,
    remove_source: bool = False,
    ffmpeg_bin: str = "ffmpeg",
) -> None:
    """合并传入目录下目标日期的监控文件。

    常见目录结构：
    indir
        2021051001
        2021051002
        2021051003

    即，子目录结构为：年月日时。
    """
    if not in_dir.exists():
        logger.error(f"{in_dir} does not exist.")
        return
    if not in_dir.is_dir():
        logger.error(f"{in_dir} is not a directory.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    videos = collect_videos_for_date(in_dir, target_date)

    logger.info(f"{target_date}, {len(videos)} videos")
    if not videos:
        logger.warning(
            f"no videos found for {target_date} in {in_dir}; "
            f"expected directories like {target_date}HH under the input directory"
        )
        return

    merge_output_dir = output_dir / date_name
    merge_output_dir.mkdir(parents=True, exist_ok=True)

    video_list_path = merge_output_dir / f"{target_date}_video_list.txt"
    write_video_list(video_list_path, videos)
    merge_videos(
        video_list_path,
        merge_output_dir / f"{target_date}.mp4",
        source_dirs=(video.parent for video in videos),
        remove_source=remove_source,
        ffmpeg_bin=ffmpeg_bin,
    )


def startup(
    input_dir: str,
    output_dir: str,
    target_date: str,
    remove_source: bool = False,
    ffmpeg_bin: str = "ffmpeg",
) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} does not exist.")
    if not input_path.is_dir():
        raise NotADirectoryError(f"{input_path} is not a directory.")

    logger.info(f"start merge {input_path.name} video for {target_date}")
    merge_dirs(
        input_path,
        output_path,
        input_path.name,
        target_date,
        remove_source=remove_source,
        ffmpeg_bin=ffmpeg_bin,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    target_date = args.date or today()
    logger.info(
        f"current time {datetime.now()},source dir : {args.indir}, "
        f"target dir: {args.outdir}, target date: {target_date}"
    )

    try:
        startup(
            args.indir,
            args.outdir,
            target_date,
            remove_source=args.delete_source,
            ffmpeg_bin=args.ffmpeg,
        )
    except (FileNotFoundError, NotADirectoryError, subprocess.CalledProcessError) as exc:
        logger.error(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
