"""Generate MP3 audio files from a JSON file containing phrases.

Usage:
  python backend/scripts/generate_audios_from_phrases.py /path/to/phrases.json

Example:
  python backend/scripts/generate_audios_from_phrases.py backend/data/phrases/go_to_college.json

This script expects a JSON structure like:
{
  "phrases": ["Phrase 1", "Phrase 2", ...]
}

For each phrase the script will create a single MP3 file named with a safe stem
in the audio output directory configured in `config.settings`.
"""
from __future__ import annotations

import argparse
import json
import re
import hashlib
from pathlib import Path
from typing import List

from config import settings
from backend.src.utils import text_to_mp3


def load_phrases(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "phrases" in data:
        phrases = data["phrases"]
    elif isinstance(data, list):
        # allow a bare list as well
        phrases = data
    else:
        raise ValueError("Unsupported JSON structure: expected object with 'phrases' or a list")

    if not isinstance(phrases, list):
        raise ValueError("'phrases' must be a list")

    return [p for p in phrases if isinstance(p, str) and p.strip()]


def safe_stem(text: str, max_len: int = 40) -> str:
    """Create a filesystem-safe stem from text; fallback to hash when necessary."""
    s = text.strip().lower()
    # replace spaces with underscores and remove undesirable chars
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_\-]", "", s)
    if not s:
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
        return f"tts_{h}"
    if len(s) > max_len:
        s = s[:max_len].rstrip("_")
    return s


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path", type=Path, help="Path to phrases JSON file")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    json_path: Path = args.json_path
    if not json_path.exists():
        raise SystemExit(f"File not found: {json_path}")

    phrases = load_phrases(json_path)
    if not phrases:
        print("No phrases found - nothing to do")
        return

    # Determine output directory: base audio dir + stem of the json filename
    audio_base = settings.AUDIO_OUTPUT_DIR
    if not Path(audio_base).is_absolute():
        audio_base = Path.cwd() / Path(audio_base)
    else:
        audio_base = Path(audio_base)

    folder_name = json_path.stem
    out_dir = audio_base / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0

    for idx, phrase in enumerate(phrases, start=1):
        stem = safe_stem(phrase)
        # ensure uniqueness by prefixing index if needed
        filename = f"{idx:02d}_{stem}"
        out_path = out_dir / f"{filename}.mp3"

        if out_path.exists() and not args.force:
            print(f"Exists, skipping: {out_path}")
            skipped += 1
            continue

        try:
            generated = text_to_mp3(phrase, filename, settings.TTS_LANG, out_path=out_path)
            print(f"Created: {generated}")
            created += 1
        except Exception as e:
            print(f"Failed to generate for phrase #{idx}: {e}")

    print(f"Done. Created: {created}, Skipped: {skipped}. Files are in: {out_dir}")


if __name__ == "__main__":
    main()
