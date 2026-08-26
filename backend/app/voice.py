"""
Local speech-to-text (D1) — faster-whisper, fully on-device.

The user explicitly chose local Whisper over the browser Web Speech API so that
microphone audio NEVER leaves this machine. Chrome's Web Speech API streams audio
to Google's servers; this module does not, and must not be replaced by anything
that does.

    transcribe(audio_bytes, filename) -> {text, language, durationMs, segments}

Safety model (this module never relaxes it):
- NO NETWORK AT INFERENCE TIME. Audio is decoded and transcribed in-process.
  The only network access faster-whisper performs is a one-time model download to
  a local cache, controlled by BRAIN_UI_WHISPER_MODEL / BRAIN_UI_WHISPER_CACHE.
  Set BRAIN_UI_WHISPER_LOCAL_ONLY=true to forbid even that.
- Transcribed text is UNTRUSTED user-adjacent content. It is returned for review
  and never auto-executed, never routed to a tool, and never treated as an
  instruction by this module.
- Uploads are size-capped and extension-checked BEFORE anything is decoded.
- Audio bytes are held in memory only; nothing is written to the vault, and the
  temp file used for decoding is always deleted.
- Model load is serialized and cached; transcription shares the agent's single
  inference gate so speech and the local LLM never compete for the GPU.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_ENV = "BRAIN_UI_WHISPER_MODEL"
DEVICE_ENV = "BRAIN_UI_WHISPER_DEVICE"
COMPUTE_ENV = "BRAIN_UI_WHISPER_COMPUTE_TYPE"
CACHE_ENV = "BRAIN_UI_WHISPER_CACHE"
LOCAL_ONLY_ENV = "BRAIN_UI_WHISPER_LOCAL_ONLY"

DEFAULT_MODEL = "base.en"
# CPU by default: the RX 7900 GRE is AMD, and faster-whisper's CUDA path does not
# apply. Ollama already owns the GPU for the local LLM.
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"

MAX_UPLOAD_BYTES = 25 * 1024 * 1024      # 25 MB
MAX_AUDIO_SECONDS = 300                  # 5 minutes
ALLOWED_SUFFIXES = frozenset({
    ".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".oga", ".webm", ".flac",
})
MAX_SEGMENTS = 500
MAX_TEXT_CHARS = 20_000

_model: Any = None
_model_key: Optional[tuple] = None
_model_lock = threading.Lock()


class VoiceError(ValueError):
    """Raised when audio cannot be transcribed safely."""


class VoiceUnavailableError(RuntimeError):
    """Raised when the local speech backend is not installed."""


# ══════════════════════════════════════════════════════════════════════════════
# Configuration / readiness
# ══════════════════════════════════════════════════════════════════════════════

def _env(source: Optional[dict]) -> dict:
    return os.environ if source is None else source


def _flag(source: dict, name: str) -> bool:
    return str(source.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def voice_config(env: Optional[dict] = None) -> dict:
    source = _env(env)
    return {
        "model": (source.get(MODEL_ENV) or DEFAULT_MODEL).strip(),
        "device": (source.get(DEVICE_ENV) or DEFAULT_DEVICE).strip(),
        "computeType": (source.get(COMPUTE_ENV) or DEFAULT_COMPUTE_TYPE).strip(),
        "cacheDir": (source.get(CACHE_ENV) or "").strip() or None,
        "localFilesOnly": _flag(source, LOCAL_ONLY_ENV),
    }


def backend_installed() -> bool:
    """True when faster-whisper is importable. Never raises."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def voice_status(env: Optional[dict] = None) -> dict:
    """Readiness for the UI. Loads no model and performs no network access."""
    installed = backend_installed()
    config = voice_config(env)
    if installed:
        message = (
            f"Local speech-to-text is available ({config['model']} on "
            f"{config['device']}). Audio is transcribed on this machine and is "
            f"never uploaded to a cloud service."
        )
    else:
        message = (
            "Local speech-to-text is not installed. Run: pip install -r requirements.txt"
        )
    return {
        "available": installed,
        "model": config["model"],
        "device": config["device"],
        "computeType": config["computeType"],
        "localFilesOnly": config["localFilesOnly"],
        "maxUploadBytes": MAX_UPLOAD_BYTES,
        "maxAudioSeconds": MAX_AUDIO_SECONDS,
        "message": message,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════════════════

def validate_upload(audio: bytes, filename: Optional[str]) -> str:
    """Check size and extension BEFORE any decode. Returns the normalized suffix."""
    if not audio:
        raise VoiceError("No audio was received.")
    if len(audio) > MAX_UPLOAD_BYTES:
        raise VoiceError(
            f"Audio is too large ({len(audio) // 1024} KB). "
            f"Limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    # Take only the basename: an uploaded filename is untrusted and must never be
    # used to build a path.
    name = Path((filename or "audio.webm").strip()).name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise VoiceError(
            f"Unsupported audio type '{suffix or 'unknown'}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}."
        )
    return suffix


# ══════════════════════════════════════════════════════════════════════════════
# Model
# ══════════════════════════════════════════════════════════════════════════════

def load_model(env: Optional[dict] = None, *, model_factory: Optional[Callable[..., Any]] = None) -> Any:
    """Load and cache the Whisper model. Serialized; safe to call concurrently."""
    global _model, _model_key

    config = voice_config(env)
    key = (config["model"], config["device"], config["computeType"], config["localFilesOnly"])

    with _model_lock:
        if _model is not None and _model_key == key:
            return _model

        factory = model_factory
        if factory is None:
            try:
                from faster_whisper import WhisperModel as factory  # type: ignore
            except Exception as exc:
                raise VoiceUnavailableError(
                    "faster-whisper is not installed. Run: pip install -r requirements.txt"
                ) from exc

        kwargs: Dict[str, Any] = {
            "device": config["device"],
            "compute_type": config["computeType"],
        }
        if config["cacheDir"]:
            kwargs["download_root"] = config["cacheDir"]
        if config["localFilesOnly"]:
            kwargs["local_files_only"] = True

        logger.info(
            "Loading local Whisper model %s (device=%s, compute=%s) — on-device only",
            config["model"], config["device"], config["computeType"],
        )
        _model = factory(config["model"], **kwargs)
        _model_key = key
        return _model


def reset_model_cache() -> None:
    """Drop the cached model (used by tests)."""
    global _model, _model_key
    with _model_lock:
        _model = None
        _model_key = None


# ══════════════════════════════════════════════════════════════════════════════
# Transcription
# ══════════════════════════════════════════════════════════════════════════════

def _acquire_inference_gate() -> Optional[Any]:
    """Share the agent's single inference gate so voice never races the LLM."""
    try:
        from app.agent import _INFERENCE_GATE, OllamaBusyError
    except Exception:  # pragma: no cover - agent module unavailable
        return None
    if not _INFERENCE_GATE.acquire(blocking=False):
        raise OllamaBusyError("Local AI is busy with another request. Try again shortly.")
    return _INFERENCE_GATE


def transcribe(
    audio: bytes,
    filename: Optional[str] = None,
    *,
    env: Optional[dict] = None,
    model: Any = None,
    language: Optional[str] = None,
) -> dict:
    """Transcribe audio locally. Returns {text, language, durationMs, segments}.

    The returned text is untrusted content: it is surfaced for the user to review
    and send deliberately. This function never routes it to a tool.
    """
    suffix = validate_upload(audio, filename)
    started = time.time()

    engine = model if model is not None else load_model(env)
    gate = _acquire_inference_gate()

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(audio)
            tmp_path = handle.name

        segments_iter, info = engine.transcribe(
            tmp_path,
            language=language or None,
            vad_filter=True,           # drop silence so short clips stay fast
            beam_size=1,
        )

        segments: List[dict] = []
        chunks: List[str] = []
        for segment in segments_iter:
            if len(segments) >= MAX_SEGMENTS:
                break
            text = str(getattr(segment, "text", "") or "").strip()
            if not text:
                continue
            segments.append({
                "start": round(float(getattr(segment, "start", 0.0) or 0.0), 2),
                "end": round(float(getattr(segment, "end", 0.0) or 0.0), 2),
                "text": text,
            })
            chunks.append(text)

        full = " ".join(chunks).strip()
        if len(full) > MAX_TEXT_CHARS:
            full = full[:MAX_TEXT_CHARS].rstrip() + "…"

        detected = str(getattr(info, "language", "") or "") or None
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        if duration > MAX_AUDIO_SECONDS:
            raise VoiceError(
                f"Audio is too long ({int(duration)}s). Limit is {MAX_AUDIO_SECONDS}s."
            )

        logger.info(
            "Local transcription complete: %d segment(s), %.1fs audio (no network, no vault write)",
            len(segments), duration,
        )
        return {
            "text": full,
            "language": detected,
            "audioSeconds": round(duration, 2),
            "durationMs": int((time.time() - started) * 1000),
            "segments": segments,
        }
    finally:
        if gate is not None:
            gate.release()
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:  # pragma: no cover - best effort cleanup
                logger.warning("Could not delete temporary audio file")
