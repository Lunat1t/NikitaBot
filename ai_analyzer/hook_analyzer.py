"""
Multimodal Hook & Virality Analyzer for NikitaBot.
Uses Google Gemini Flash to evaluate the first 3 seconds of Reels (visual frames + transcript + caption).
Includes intelligent local heuristic fallback when running offline or without API keys.
"""

import os
import json
import base64
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("NikitaBot.HookAnalyzer")


class HookAnalyzer:
    """
    Analyzes Reels hooks using Google Gemini Flash or heuristic fallback.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model

    def analyze(
        self,
        frame_paths: List[str],
        transcript: str = "",
        caption: str = "",
        tags: Optional[List[str]] = None,
        likes: int = 0,
        comments: int = 0
    ) -> Dict[str, Any]:
        """
        Runs multimodal evaluation of the hook.

        Args:
            frame_paths: List of file paths to 3 hook JPEG frames (0.5s, 1.5s, 3.0s).
            transcript: Transcribed speech from faster-whisper.
            caption: Original post caption.
            tags: Hashtags list.
            likes: Number of likes.
            comments: Number of comments.

        Returns:
            Dict containing:
                - hook_score: float (1.0 to 10.0)
                - virality_score: int (1 to 100)
                - hook_type: str (e.g. 'Curiosity Gap', 'Visual Shock', etc.)
                - hook_dynamics: str
                - summary: str
                - retention_prediction: str ('High' | 'Medium' | 'Low')
                - engine: 'gemini-flash' or 'heuristic-fallback'
        """
        tags = tags or []

        if self.api_key:
            try:
                result = self._analyze_with_gemini(frame_paths, transcript, caption, tags)
                if result:
                    result["engine"] = "gemini-flash"
                    return result
            except Exception as e:
                logger.warning(f"Gemini Flash analysis failed ({e}), falling back to heuristic engine.")

        # Heuristic fallback (offline / no API key)
        return self._analyze_heuristic(frame_paths, transcript, caption, tags, likes, comments)

    def _analyze_with_gemini(
        self,
        frame_paths: List[str],
        transcript: str,
        caption: str,
        tags: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Invokes Gemini Multimodal API via google-genai or direct HTTP."""
        import urllib.request

        image_parts = []
        for p in frame_paths:
            if os.path.exists(p):
                with open(p, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                    image_parts.append({
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": data
                        }
                    })

        prompt_text = f"""
You are an elite viral content strategist and Instagram Reels hook expert.
Analyze the first 3 seconds of this Reel (3 sequential keyframes at 0.5s, 1.5s, 3.0s, plus the spoken transcript and caption).

Metadata:
- Spoken Audio Transcript: "{transcript}"
- Post Caption: "{caption[:500]}"
- Tags: {', '.join(tags[:10])}

Evaluate:
1. Hook Rating: 1.0 to 10.0 (strength of the pattern interrupt and grab)
2. Virality Score: 1 to 100
3. Hook Type: One of ["Visual Shock", "Curiosity Gap", "Problem-Agitate", "Pattern Interrupt", "Contrarian Statement", "Story Teaser", "Meme/Relatable"]
4. Pacing & Dynamics: Short observation on visual motion/composition across the 3 frames
5. Retention Prediction: "High", "Medium", or "Low"
6. Summary: 2 concise sentences on why this hook works/fails and how to improve it.

Return ONLY a valid JSON object matching this schema:
{{
  "hook_score": 8.5,
  "virality_score": 88,
  "hook_type": "Curiosity Gap",
  "pacing_dynamics": "High dynamic change between frame 1 and 2, fast visual transition",
  "retention_prediction": "High",
  "summary": "Clear curiosity trigger combined with rapid visual cut keeps the viewer hooked."
}}
"""

        parts = [{"text": prompt_text}] + image_parts
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json"
            }
        }

        # Direct REST request to avoid heavy SDK dependencies
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text_resp = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text_resp)
            return {
                "hook_score": float(parsed.get("hook_score", 7.0)),
                "virality_score": int(parsed.get("virality_score", 75)),
                "hook_type": str(parsed.get("hook_type", "Pattern Interrupt")),
                "hook_dynamics": str(parsed.get("pacing_dynamics", "Стабильный видеоряд")),
                "retention_prediction": str(parsed.get("retention_prediction", "Medium")),
                "summary": str(parsed.get("summary", "Контент проверен и оценен."))
            }

    def _analyze_heuristic(
        self,
        frame_paths: List[str],
        transcript: str,
        caption: str,
        tags: List[str],
        likes: int,
        comments: int
    ) -> Dict[str, Any]:
        """Heuristic rule-based analyzer when no API key is provided."""
        text_corpus = f"{transcript} {caption}".lower()

        # Check for hook trigger words
        curiosity_triggers = ["почему", "секрет", "как я", "никогда не", "шок", "лайфхак", "топ 5", "ошибка", "правда"]
        has_trigger = any(w in text_corpus for w in curiosity_triggers)

        # Frame count bonus
        frame_count = len([p for p in frame_paths if os.path.exists(p)])

        # Engagement factor
        engagement = likes + (comments * 3)

        if has_trigger:
            hook_score = 8.8 if frame_count >= 3 else 8.2
            virality = 85 if frame_count >= 3 else 80
            hook_type = "Curiosity Gap (Любопытство)"
            retention = "High"
            summary = "Сильный вербальный триггер в первые секунды с высокой интригой."
        elif frame_count >= 3:
            hook_score = 7.4
            virality = 72
            hook_type = "Pattern Interrupt (Смена кадров)"
            retention = "Medium"
            summary = "Хорошая динамика смены кадров (0.5с - 3.0с), удерживает визуальное внимание."
        elif transcript:
            hook_score = 6.8
            virality = 65
            hook_type = "Story Teaser (Повествование)"
            retention = "Medium"
            summary = "Четкая голосовая подача с первых секунд, рекомендуется добавить контрастный текст на экран."
        else:
            hook_score = 5.5
            virality = 50
            hook_type = "Visual Flow (Визуальный поток)"
            retention = "Low"
            summary = "Хук умеренной силы. Для роста виральности рекомендуется добавить яркую проблему в первые 2 секунды."

        if engagement > 5000:
            virality = min(99, virality + 10)
            hook_score = min(9.9, hook_score + 0.8)

        return {
            "hook_score": round(hook_score, 1),
            "virality_score": int(virality),
            "hook_type": hook_type,
            "hook_dynamics": f"Извлечено {frame_count} ключевых кадров хука за первые 3 секунды.",
            "retention_prediction": retention,
            "summary": summary,
            "engine": "heuristic-fallback"
        }
