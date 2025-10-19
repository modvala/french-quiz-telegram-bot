"""Text-to-speech utilities using gTTS.

Provides a simple helper to generate MP3 pronunciation files.
"""
from pathlib import Path
from typing import Optional, Union

try:
    from gtts import gTTS
except Exception:  # pragma: no cover - imported at runtime
    gTTS = None


def text_to_mp3(
    text: str,
    filename: str,
    lang: str,
    out_path: Union[str, Path],
) -> Path:
    """Generate an MP3 file pronouncing `text` using gTTS.

    Args:
        text: Text to pronounce.
        filename: Optional file name (without extension). If omitted a safe name is generated.
        lang: Language code for TTS (default 'fr').
        out_path: Path where the MP3 file should be saved. Can be a directory or full filepath.

    Returns:
        Path to the generated MP3 file.

    Raises:
        RuntimeError: if gTTS is not installed or generation fails.
    """
    if gTTS is None:
        raise RuntimeError(
            "gTTS is not installed. Add 'gTTS' to your requirements and install it."
        )

    if not text:
        raise ValueError("text must be non-empty")

    # Resolve output path
    out_p = Path(out_path)
    # if user provided a directory, use filename or generated name
    if out_p.suffix.lower() != ".mp3":
        # treat as directory
        out_p.mkdir(parents=True, exist_ok=True)
        safe_name = (filename or "").strip()
        if not safe_name:
            import hashlib

            h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
            safe_name = f"tts_{h}"
        out_p = out_p / f"{safe_name}.mp3"
    else:
        # ensure parent exists
        out_p.parent.mkdir(parents=True, exist_ok=True)

    tts = gTTS(text=text, lang=lang)
    tts.save(str(out_p))

    return out_p
