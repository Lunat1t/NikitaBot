"""Unit tests for MediaProcessor (FFmpeg audio & hook frame extraction)."""
import os
import shutil
import subprocess
import tempfile
import unittest

from processor.media import extract_audio, extract_hook_frames, cleanup_video, get_video_duration


class TestMediaProcessor(unittest.TestCase):
    """Tests for FFmpeg video processing."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="nikitabot_media_test_")
        cls.test_video = os.path.join(cls.test_dir, "sample.mp4")

        # Generate a synthetic 4-second test MP4 using ffmpeg lavfi
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi", "-i", "testsrc=duration=4.0:size=320x240:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4.0",
            "-loglevel", "error",
            cls.test_video
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception as e:
            raise unittest.SkipTest(f"FFmpeg synthetic video generation not supported: {e}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_get_video_duration(self):
        duration = get_video_duration(self.test_video)
        self.assertGreater(duration, 3.0)

    def test_02_extract_audio(self):
        wav_path = os.path.join(self.test_dir, "extracted.wav")
        result_path = extract_audio(self.test_video, wav_path)
        self.assertIsNotNone(result_path)
        self.assertTrue(os.path.exists(wav_path))
        self.assertGreater(os.path.getsize(wav_path), 1000)

    def test_03_extract_hook_frames(self):
        thumbnails_dir = os.path.join(self.test_dir, "thumbs")
        frames = extract_hook_frames(
            self.test_video,
            output_dir=thumbnails_dir,
            timestamps=(0.5, 1.5, 3.0),
            shortcode="test123"
        )
        self.assertEqual(len(frames), 3)
        for f in frames:
            self.assertTrue(os.path.exists(f))
            self.assertGreater(os.path.getsize(f), 500)

    def test_04_cleanup_video(self):
        # Create a temp copy of video to test deletion
        temp_copy = os.path.join(self.test_dir, "copy_to_delete.mp4")
        shutil.copy(self.test_video, temp_copy)
        self.assertTrue(os.path.exists(temp_copy))

        res = cleanup_video(temp_copy)
        self.assertTrue(res)
        self.assertFalse(os.path.exists(temp_copy))


if __name__ == "__main__":
    unittest.main()
