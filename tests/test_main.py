import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class MainTestCase(unittest.TestCase):
    def test_format_concat_line_quotes_spaces_and_single_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "camera clips" / "clip's 01.mp4"
            video.parent.mkdir()
            video.touch()

            line = main.format_concat_line(video)

            self.assertTrue(line.startswith("file '"))
            self.assertTrue(line.endswith("'"))
            self.assertIn("camera clips", line)
            self.assertIn("clip'\\''s 01.mp4", line)

    def test_merge_videos_keeps_sources_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "camera day"
            source_dir.mkdir()
            video = source_dir / "clip 1.mp4"
            video.touch()
            list_file = Path(tmp) / "video_list.txt"
            list_file.write_text(main.format_concat_line(video), encoding="utf8")
            target_file = Path(tmp) / "out" / "20240101.mp4"

            with patch("main.subprocess.run") as run:
                main.merge_videos(
                    list_file,
                    target_file,
                    source_dirs=[source_dir],
                    ffmpeg_bin="ffmpeg-test",
                )

            run.assert_called_once()
            self.assertTrue(source_dir.exists())
            self.assertFalse(list_file.exists())

    def test_merge_videos_deletes_sources_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "camera day"
            source_dir.mkdir()
            video = source_dir / "clip 1.mp4"
            video.touch()
            list_file = Path(tmp) / "video_list.txt"
            list_file.write_text(main.format_concat_line(video), encoding="utf8")
            target_file = Path(tmp) / "out" / "20240101.mp4"

            with patch("main.subprocess.run") as run:
                main.merge_videos(
                    list_file,
                    target_file,
                    source_dirs=[source_dir],
                    remove_source=True,
                    ffmpeg_bin="ffmpeg-test",
                )

            run.assert_called_once()
            cmd = run.call_args.args[0]
            self.assertIsInstance(cmd, list)
            self.assertEqual(cmd[0], "ffmpeg-test")
            self.assertIn(str(list_file), cmd)
            self.assertIn(str(target_file), cmd)
            self.assertEqual(run.call_args.kwargs, {"check": True})
            self.assertFalse(source_dir.exists())
            self.assertFalse(list_file.exists())

    def test_main_defaults_to_today_and_keeps_sources(self):
        with patch("main.today", return_value="20240101"), patch("main.startup") as startup:
            self.assertEqual(main.main(["/input", "--outdir", "/output"]), 0)
            self.assertFalse(startup.call_args.kwargs["remove_source"])
            self.assertEqual(startup.call_args.args[2], "20240101")

    def test_main_deletes_sources_only_when_delete_source_is_passed(self):
        with patch("main.startup") as startup:
            self.assertEqual(
                main.main(
                    [
                        "/input",
                        "--outdir",
                        "/output",
                        "--date",
                        "20240102",
                        "--delete-source",
                    ]
                ),
                0,
            )
            self.assertTrue(startup.call_args.kwargs["remove_source"])
            self.assertEqual(startup.call_args.args[2], "20240102")

    def test_keep_source_argument_was_removed(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main.parse_args(["/input", "--keep-source"])

    def test_merge_videos_keeps_sources_when_ffmpeg_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "camera"
            source_dir.mkdir()
            video = source_dir / "clip.mp4"
            video.touch()
            list_file = Path(tmp) / "video_list.txt"
            list_file.write_text(main.format_concat_line(video), encoding="utf8")
            target_file = Path(tmp) / "out" / "20240101.mp4"

            with patch("main.subprocess.run") as run:
                run.side_effect = subprocess.CalledProcessError(1, ["ffmpeg"])
                with self.assertRaises(subprocess.CalledProcessError):
                    main.merge_videos(list_file, target_file, source_dirs=[source_dir])

            self.assertTrue(source_dir.exists())
            self.assertTrue(list_file.exists())

    def test_merge_dirs_writes_naturally_sorted_concat_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            camera_dir = Path(tmp) / "camera"
            day_dir = camera_dir / "2024010101"
            day_dir.mkdir(parents=True)
            for name in ["clip_10.mp4", "clip_2.mp4", "clip_1.mp4"]:
                (day_dir / name).touch()
            output_dir = Path(tmp) / "output"

            with patch("main.merge_videos") as merge_videos:
                main.merge_dirs(
                    camera_dir,
                    output_dir,
                    "camera",
                    "20240101",
                    remove_source=False,
                )

            merge_videos.assert_called_once()
            list_file = merge_videos.call_args.args[0]
            target_file = merge_videos.call_args.args[1]
            lines = list_file.read_text(encoding="utf8").splitlines()

            self.assertEqual(target_file, output_dir / "camera" / "20240101.mp4")
            self.assertTrue(lines[0].endswith("clip_1.mp4'"))
            self.assertTrue(lines[1].endswith("clip_2.mp4'"))
            self.assertTrue(lines[2].endswith("clip_10.mp4'"))

    def test_merge_dirs_only_collects_target_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            camera_dir = Path(tmp) / "camera"
            target_day_dir = camera_dir / "2024010101"
            old_day_dir = camera_dir / "2024010201"
            target_day_dir.mkdir(parents=True)
            old_day_dir.mkdir(parents=True)
            (target_day_dir / "clip_1.mp4").touch()
            (old_day_dir / "clip_1.mp4").touch()
            output_dir = Path(tmp) / "output"

            with patch("main.merge_videos") as merge_videos:
                main.merge_dirs(
                    camera_dir,
                    output_dir,
                    "camera",
                    "20240101",
                    remove_source=False,
                )

            list_file = merge_videos.call_args.args[0]
            lines = list_file.read_text(encoding="utf8").splitlines()

            self.assertEqual(len(lines), 1)
            self.assertIn("2024010101", lines[0])
            self.assertNotIn("2024010201", lines[0])

    def test_merge_dirs_does_not_enter_camera_id_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "xiaomi_camera_videos"
            camera_id_dir = input_dir / "607ea4141671" / "2024010101"
            camera_id_dir.mkdir(parents=True)
            (camera_id_dir / "clip_1.mp4").touch()
            output_dir = Path(tmp) / "output"

            with patch("main.merge_videos") as merge_videos:
                main.merge_dirs(
                    input_dir,
                    output_dir,
                    input_dir.name,
                    "20240101",
                    remove_source=False,
                )

            merge_videos.assert_not_called()

    def test_startup_processes_only_input_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            input_dir.mkdir()
            output_dir = Path(tmp) / "output"

            with patch("main.merge_dirs") as merge_dirs:
                main.startup(
                    str(input_dir),
                    str(output_dir),
                    "20240101",
                    remove_source=False,
                )

            merge_dirs.assert_called_once()
            self.assertEqual(merge_dirs.call_args.args[0], input_dir)
            self.assertEqual(merge_dirs.call_args.args[2], "input")
            self.assertEqual(merge_dirs.call_args.args[3], "20240101")


if __name__ == "__main__":
    unittest.main()
