"""Audio transcription — turn an audio file into a timestamped transcript.

v0.1 uses OpenAI's Whisper API (``whisper-1``). The ``openai`` package and
``OPENAI_API_KEY`` are required. Files must be <= 25 MB (Whisper API limit).
Automatic chunking of longer audio is planned for v0.2 — until then, split
with ffmpeg first.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


WHISPER_MAX_BYTES = 25 * 1024 * 1024  # 25 MB


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "text": self.text}


@dataclass
class TranscriptResult:
    audio_path: Path
    text: str
    language: str | None
    duration: float | None
    model: str
    segments: list[TranscriptSegment] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "audio_path": str(self.audio_path),
            "text": self.text,
            "language": self.language,
            "duration": self.duration,
            "model": self.model,
            "segments": [s.as_dict() for s in self.segments],
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=2) + "\n")

    def write_text(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.text + "\n")


def _validate_audio(audio_path: Path) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    if not audio_path.is_file():
        raise ValueError(f"not a regular file: {audio_path}")
    size = audio_path.stat().st_size
    if size == 0:
        raise ValueError(f"audio file is empty: {audio_path}")
    if size > WHISPER_MAX_BYTES:
        mb = size / 1024 / 1024
        raise ValueError(
            f"audio file is {mb:.1f} MB; Whisper API limit is 25 MB. "
            f"Split with ffmpeg first, e.g.\n"
            f"  ffmpeg -i in.m4a -f segment -segment_time 600 -c copy out%d.m4a\n"
            f"Automatic chunking is planned for v0.2."
        )


def transcribe(
    audio_path: Path | str,
    *,
    model: str = "whisper-1",
    language: str | None = None,
    prompt: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> TranscriptResult:
    """Transcribe ``audio_path`` via OpenAI Whisper.

    Args:
        audio_path: local audio file (<= 25 MB, see WHISPER_MAX_BYTES).
        model: Whisper model name (default ``whisper-1``).
        language: BCP-47 language code to bias detection (e.g. ``"en"``).
        prompt: short text to prime vocabulary / style.
        api_key: override ``OPENAI_API_KEY``.
        base_url: override the OpenAI API base URL (useful for compatible proxies).

    Returns:
        TranscriptResult with full text, per-segment timestamps, language
        and duration.

    Raises:
        FileNotFoundError: audio path does not exist.
        ValueError: audio is empty, too large, or not a regular file.
        ImportError: the ``openai`` package is not installed.
    """
    audio_path = Path(audio_path)
    _validate_audio(audio_path)

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "transcribe requires the 'openai' package. "
            "Install: pip install 'videoink[openai]'"
        ) from None

    client_kwargs: dict[str, Any] = {"api_key": api_key or os.getenv("OPENAI_API_KEY")}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    req_kwargs: dict[str, Any] = {
        "model": model,
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment"],
    }
    if language:
        req_kwargs["language"] = language
    if prompt:
        req_kwargs["prompt"] = prompt

    with audio_path.open("rb") as fh:
        raw = client.audio.transcriptions.create(file=fh, **req_kwargs)

    data: dict[str, Any] = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
    segments_data = data.get("segments") or []
    segments = [
        TranscriptSegment(
            start=float(s.get("start", 0.0)),
            end=float(s.get("end", 0.0)),
            text=str(s.get("text", "")).strip(),
        )
        for s in segments_data
    ]

    duration_raw = data.get("duration")
    return TranscriptResult(
        audio_path=audio_path,
        text=str(data.get("text", "")).strip(),
        language=data.get("language"),
        duration=float(duration_raw) if duration_raw is not None else None,
        model=model,
        segments=segments,
    )
