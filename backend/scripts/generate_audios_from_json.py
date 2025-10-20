"""Generate MP3 audio files from a JSON questions file.

Usage: python scripts/generate_audios_from_json.py /path/to/questions.json

Supported input formats:
- Legacy: top-level array of question objects (each may contain 'audio').
- New: top-level object with key 'questions' containing the array.

For each question the script generates two MP3 files:
- One for the country name
- One for the answer (nationality)

If an item has an 'audio' field the script will reuse its stem as a base name.
Otherwise files are named using the question id (e.g. q1_answer.mp3, q1_country.mp3).
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

    # Support both legacy (list) and new (dict with 'questions') formats
    if isinstance(data, dict):
        items = data.get("questions") or []
    elif isinstance(data, list):
        items = data
    else:
        print("Unsupported JSON structure - expected list or object with 'questions'.")
        raise SystemExit(2)

    created = 0
    skipped = 0

    for idx, item in enumerate(items, start=1):
        # Use q{ID} as base name for all generated audio files to keep naming consistent
        qid = item.get("id") or idx
        audio_rel = item.get("audio")  # original (if any) - we'll overwrite below

        # Get the text content
        answer_text = item.get("answer")
        country_text = item.get("country")

        if not answer_text and not country_text:
            print(f"Skipping item {qid}: no text content")
            skipped += 1
            continue

        # Use AUDIO_DIR as base for output paths
        # Always use q{qid} as the base name for generated files
        audio_name = f"q{qid}"

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

        # Generate files for available texts
        if answer_text:
            gen_one(answer_text, answer_path)
        else:
            print(f"No answer text for item {qid}")
            skipped += 1

        if country_text:
            gen_one(country_text, country_path)
        else:
            print(f"No country text for item {qid}")
            skipped += 1

        # Update the item's audio field to point to the canonical base (so backend can resolve _answer/_country)
        # We store the .mp3 value; backend._audio_url will try variants like _answer/_country
        if isinstance(data, dict) and data.get("questions") is items:
            item["audio"] = f"audio/{audio_name}.mp3"
        elif isinstance(data, list):
            item["audio"] = f"audio/{audio_name}.mp3"

    print(f"Done. Created: {created}, Skipped: {skipped}")

    # Persist changes to JSON (update audio fields)
    try:
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Updated JSON file with audio paths: {json_path}")
    except Exception as e:
        print(f"Failed to update JSON file: {e}")


if __name__ == "__main__":
    main()
