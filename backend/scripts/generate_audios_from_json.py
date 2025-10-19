"""Generate MP3 audio files from a JSON questions file.

Usage: python scripts/generate_audios_from_json.py /path/to/questions.json

For each item in the top-level array, the script generates two MP3 files:
- One for the country name
- One for the answer (nationality)
Files are saved according to paths in the 'audio' field.
"""
import json
import sys
from pathlib import Path
from typing import Any

from backend.src.utils import text_to_mp3
from config import settings


# Get audio directory from settings
AUDIO_DIR = settings.AUDIO_OUTPUT_DIR
if not AUDIO_DIR.is_absolute():
    AUDIO_DIR = Path.cwd() / AUDIO_DIR


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_audios_from_json.py /path/to/questions.json")
        print("Example: python backend/scripts/generate_audios_from_json.py backend/data/nationalies/questions.json")
        raise SystemExit(2)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"File not found: {json_path}")
        raise SystemExit(2)

    data = load_json(json_path)
    if not isinstance(data, list):
        print("Expected a top-level JSON array of questions.")
        raise SystemExit(2)

    created = 0
    skipped = 0

    for item in data:
        audio_rel = item.get("audio")
        if not audio_rel:
            print("Skipping item without 'audio' field", item.get("id"))
            skipped += 1
            continue

        # Get the text content
        answer_text = item.get("answer")
        country_text = item.get("country")

        if not answer_text and not country_text:
            print(f"Skipping item {item.get('id')}: no text content")
            skipped += 1
            continue

        # Use AUDIO_DIR as base for output paths
        audio_name = Path(audio_rel).stem
        answer_path = AUDIO_DIR / f"{audio_name}_answer.mp3"
        country_path = AUDIO_DIR / f"{audio_name}_country.mp3"

        def gen_one(text: str, path: Path) -> bool:
            nonlocal created, skipped
            if not text:
                print(f"No text for {path.name}")
                skipped += 1
                return False
            if path.exists():
                print(f"Exists, skipping: {path}")
                skipped += 1
                return False

            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                # backend.src.utils.text_to_mp3 requires a filename arg; derive it from path
                filename = path.stem
                # use configured TTS language
                generated = text_to_mp3(text, filename, settings.TTS_LANG, out_path=path)
                print(f"Created: {generated}")
                created += 1
                return True
            except Exception as e:
                print(f"Failed to create {path}: {e}")
                return False

        # Generate both files if text is available
        if answer_text:
            gen_one(answer_text, answer_path)
        else:
            print(f"No answer text for item {item.get('id')}")
            skipped += 1

        if country_text:
            gen_one(country_text, country_path)
        else:
            print(f"No country text for item {item.get('id')}")
            skipped += 1

    print(f"Done. Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
