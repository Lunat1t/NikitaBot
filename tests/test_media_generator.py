import os
import unittest
from scraper.media_generator import generate_reel_video
from processor.media import extract_hook_frames, extract_audio

class TestMediaGenerator(unittest.TestCase):
    def test_generate_and_extract_media(self):
        shortcode = "test_synth_reel_99"
        username = "test_creator"
        hook_text = "3 секрета привлечения клиентов через короткие видео"
        
        video_path = generate_reel_video(shortcode, username, hook_text, duration=4)
        self.assertTrue(os.path.exists(video_path))
        self.assertGreater(os.path.getsize(video_path), 1000)

        # Extract frames
        thumbs_dir = os.path.join("data", "thumbnails")
        frames = extract_hook_frames(video_path, output_dir=thumbs_dir, timestamps=(0.5, 1.5, 3.0), shortcode=shortcode)
        self.assertEqual(len(frames), 3)
        for f in frames:
            self.assertTrue(os.path.exists(f))

        # Extract audio
        wav = extract_audio(video_path)
        self.assertIsNotNone(wav)
        self.assertTrue(os.path.exists(wav))

if __name__ == "__main__":
    unittest.main()
