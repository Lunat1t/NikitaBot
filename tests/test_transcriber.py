"""Unit tests for WhisperTranscriber."""
import os
import tempfile
import unittest

from processor.transcriber import WhisperTranscriber


class TestWhisperTranscriber(unittest.TestCase):
    """Tests for Whisper speech-to-text integration."""

    def setUp(self):
        self.transcriber = WhisperTranscriber(model_size="base")

    def test_01_init_transcriber(self):
        self.assertEqual(self.transcriber.model_size, "base")
        self.assertEqual(self.transcriber.device, "cpu")

    def test_02_missing_file_handling(self):
        result = self.transcriber.transcribe("/non/existent/audio.wav")
        self.assertIn("text", result)
        self.assertEqual(result["text"], "")

    def test_03_fallback_transcription(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tf.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
            temp_path = tf.name

        try:
            # If faster_whisper is not installed, fallback format is verified
            if not self.transcriber.is_available:
                res = self.transcriber.transcribe(temp_path)
                self.assertTrue(len(res["text"]) > 0)
                self.assertIn("segments", res)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
