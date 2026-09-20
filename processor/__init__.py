"""Media processing and speech-to-text package for NikitaBot."""
from .media import extract_audio, extract_hook_frames, get_video_duration, cleanup_video
from .transcriber import WhisperTranscriber

__all__ = [
    "extract_audio",
    "extract_hook_frames",
    "get_video_duration",
    "cleanup_video",
    "WhisperTranscriber"
]
