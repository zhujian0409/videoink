"""Audio transcription — turn an audio file into a timestamped transcript.

Two engines are supported:

* ``openai`` (default): OpenAI Whisper API (``whisper-1``). Requires the
  ``openai`` package and ``OPENAI_API_KEY``. Files must be <= 25 MB.
* ``local``: offline ``faster-whisper`` (CTranslate2). No API key, no
  size cap, CPU-friendly. Requires the ``faster-whisper`` package and
  downloads the chosen model (~150 MB for ``base``) on first use.

``local`` is the default for skill-native usage (Claude Code / Codex),
``openai`` is provided for pure-CLI / CI scenarios where a managed API
is preferred.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


WHISPER_MAX_BYTES = 25 * 1024 * 1024  # 25 MB — openai engine only

Engine = Literal["openai", "local"]


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
    engine: str = "openai"
    segments: list[TranscriptSegment] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "audio_path": str(self.audio_path),
            "text": self.text,
            "language": self.language,
            "duration": self.duration,
            "model": self.model,
            "engine": self.engine,
            "segments": [s.as_dict() for s in self.segments],
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=2) + "\n")

    def write_text(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.text + "\n")


def _validate_audio(audio_path: Path, *, enforce_size_cap: bool = True) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    if not audio_path.is_file():
        raise ValueError(f"not a regular file: {audio_path}")
    size = audio_path.stat().st_size
    if size == 0:
        raise ValueError(f"audio file is empty: {audio_path}")
    if enforce_size_cap and size > WHISPER_MAX_BYTES:
        mb = size / 1024 / 1024
        raise ValueError(
            f"audio file is {mb:.1f} MB; Whisper API limit is 25 MB. "
            f"Options: (1) split with ffmpeg "
            f"(`ffmpeg -i in.m4a -f segment -segment_time 600 -c copy out%d.m4a`); "
            f"(2) use --engine local (no size cap)."
        )


def transcribe(
    audio_path: Path | str,
    *,
    engine: Engine = "openai",
    model: str | None = None,
    language: str | None = None,
    prompt: str | None = None,
    # openai engine knobs
    api_key: str | None = None,
    base_url: str | None = None,
    # local engine knobs
    compute_type: str = "int8",
    device: str = "cpu",
) -> TranscriptResult:
    """Transcribe ``audio_path``.

    Args:
        engine: ``"openai"`` (API) or ``"local"`` (faster-whisper).
        model: model id. Default depends on engine: ``whisper-1`` for
            openai, ``base`` for local. Other local options: ``tiny``,
            ``small``, ``medium``, ``large-v3``.
        language: BCP-47 code (e.g. ``"en"``).
        prompt: short text to prime vocabulary / style.
        api_key, base_url: override OPENAI_API_KEY / base URL (openai only).
        compute_type, device: passed to faster-whisper (local only).
    """
    audio_path = Path(audio_path)

    if engine == "openai":
        _validate_audio(audio_path, enforce_size_cap=True)
        return _transcribe_openai(
            audio_path,
            model=model or "whisper-1",
            language=language,
            prompt=prompt,
            api_key=api_key,
            base_url=base_url,
        )
    if engine == "local":
        _validate_audio(audio_path, enforce_size_cap=False)
        return _transcribe_local(
            audio_path,
            model=model or "base",
            language=language,
            prompt=prompt,
            compute_type=compute_type,
            device=device,
        )
    raise ValueError(f"unknown transcribe engine: {engine!r}")


def _transcribe_openai(
    audio_path: Path,
    *,
    model: str,
    language: str | None,
    prompt: str | None,
    api_key: str | None,
    base_url: str | None,
) -> TranscriptResult:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "transcribe --engine openai requires the 'openai' package. "
            "Install: pip install 'videoink[openai]' (or use --engine local)"
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
        engine="openai",
        segments=segments,
    )


def _transcribe_local(
    audio_path: Path,
    *,
    model: str,
    language: str | None,
    prompt: str | None,
    compute_type: str,
    device: str,
) -> TranscriptResult:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "transcribe --engine local requires the 'faster-whisper' package. "
            "Install: pip install 'videoink[local]' (or use --engine openai)"
        ) from None

    whisper_model = WhisperModel(model, device=device, compute_type=compute_type)
    segments_iter, info = whisper_model.transcribe(
        str(audio_path),
        language=language,
        initial_prompt=prompt,
        vad_filter=True,
    )

    segments: list[TranscriptSegment] = []
    text_parts: list[str] = []
    for seg in segments_iter:
        text = seg.text.strip()
        segments.append(TranscriptSegment(start=float(seg.start), end=float(seg.end), text=text))
        text_parts.append(seg.text)

    return TranscriptResult(
        audio_path=audio_path,
        text=" ".join(text_parts).strip(),
        language=info.language,
        duration=float(info.duration),
        model=model,
        engine="local",
        segments=segments,
    )
