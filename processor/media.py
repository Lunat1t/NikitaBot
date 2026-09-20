"""
Media Processing Module for NikitaBot.
Handles audio extraction (16kHz mono WAV for Whisper),
hook keyframe extraction (0.5s, 1.5s, 3.0s for Gemini Vision),
and video file cleanup for disk space saving.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("NikitaBot.MediaProcessor")


def extract_audio(video_path: str, output_wav_path: Optional[str] = None, sample_rate: int = 16000) -> Optional[str]:
    """
    Extracts mono WAV audio from a video file formatted for Whisper (16kHz, 16-bit PCM).

    Args:
        video_path: Path to the input video file (e.g., MP4).
        output_wav_path: Optional destination WAV path. If None, uses same name with .wav.
        sample_rate: Audio sampling rate (default 16000 Hz).

    Returns:
        Path to the generated WAV file, or None if extraction failed.
    """
    if not os.path.exists(video_path):
        logger.error(f"Input video does not exist: {video_path}")
        return None

    if output_wav_path is None:
        video_p = Path(video_path)
        output_wav_path = str(video_p.with_suffix(".wav"))

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-loglevel", "error",
        str(output_wav_path)
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0:
            logger.info(f"Extracted audio to {output_wav_path}")
            return output_wav_path
        else:
            logger.warning(f"Audio extraction created empty file: {output_wav_path}")
            return None
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg audio extraction error: {e.stderr}")
        return None
    except FileNotFoundError:
        logger.error("FFmpeg binary not found on the system.")
        return None


def extract_hook_frames(
    video_path: str,
    output_dir: str,
    timestamps: Tuple[float, ...] = (0.5, 1.5, 3.0),
    shortcode: str = "reel"
) -> List[str]:
    """
    Extracts keyframes from the first seconds of a video (the 'hook' window).

    Args:
        video_path: Path to the input video file.
        output_dir: Directory where JPEG frames will be saved.
        timestamps: Seconds into video to sample (e.g. 0.5s, 1.5s, 3.0s).
        shortcode: Unique reel identifier for filename prefixing.

    Returns:
        List of absolute file paths to the generated JPEG frames.
    """
    if not os.path.exists(video_path):
        logger.error(f"Input video does not exist: {video_path}")
        return []

    os.makedirs(output_dir, exist_ok=True)
    frame_paths = []

    for idx, ts in enumerate(timestamps, start=1):
        out_filename = f"{shortcode}_hook_{idx}_{ts}s.jpg"
        out_path = os.path.join(output_dir, out_filename)

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(ts),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            "-loglevel", "error",
            str(out_path)
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                frame_paths.append(out_path)
                logger.info(f"Extracted hook frame #{idx} ({ts}s) -> {out_path}")
            else:
                logger.warning(f"Frame at {ts}s was empty or skipped.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Could not extract frame at {ts}s: {e}")

    return frame_paths


def get_video_duration(video_path: str) -> float:
    """Returns the video duration in seconds via ffprobe."""
    if not os.path.exists(video_path):
        return 0.0

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def cleanup_video(video_path: str) -> bool:
    """
    Deletes the source MP4 video file to preserve storage space.
    Hook frames and extracted audio WAV are kept.
    """
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            logger.info(f"Cleaned up source video: {video_path}")
            return True
    except OSError as e:
        logger.error(f"Failed to delete video {video_path}: {e}")
    return False
