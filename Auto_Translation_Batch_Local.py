"""
auto_translation_batch.py
─────────────────────────────────────────────────────────────────────────────
Batch translation script using Google Translate via Selenium.

Scans an input folder for .txt / .csv files, translates all phrases in
each file, and writes a numbered output CSV to the output folder.

Output naming:  rough_L_1.csv, rough_L_2.csv, rough_L_3.csv …

HOW TO RUN LOCALLY (VS Code)
─────────────────────────────────────────────────────────────────────────────
1. Install dependencies:
       pip install selenium webdriver-manager

2. Chrome must be installed on your machine.
   The script auto-downloads the matching ChromeDriver via webdriver-manager.

3. Edit the CONFIG section below (input/output folder paths, languages).

4. Place your .txt or .csv files in the INPUT_FOLDER.

5. Run:
       python auto_translation_batch.py

INPUT FILE FORMATS
─────────────────────────────────────────────────────────────────────────────
• .txt  →  each line: "id, phrase"   (comma-separated, one phrase per line)
• .csv  →  with or without a header row
           Columns are auto-detected by name (id, english/eng, hiligaynon/hil)
           Falls back to first two columns if no named headers are found.
─────────────────────────────────────────────────────────────────────────────
"""

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import csv
import logging
import os
import sys
import time
import urllib.parse
from pathlib import Path
from typing import List, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG  ← static settings (paths are asked at runtime)
# ══════════════════════════════════════════════════════════════════════════════

OUTPUT_PREFIX  = "rough_L"         # Output file prefix  →  rough_L_1.csv, rough_L_2.csv …

SOURCE_LANG    = "en"               # Source language code (e.g. "en")
TARGET_LANG    = "hil"              # Target language code (e.g. "hil" = Hiligaynon)
TARGET_COLUMN  = "hiligaynon"       # Name of the translated column in the output CSV

SUPPORTED_EXTS = {".txt", ".csv"}  # File extensions to process

DELAY          = 2.0                # Seconds to wait after each translation
RETRY_COUNT    = 3                  # How many times to retry a blank translation
SAVE_EVERY     = 50                 # Save progress checkpoint every N phrases


# ══════════════════════════════════════════════════════════════════════════════
#  RUNTIME PATH PROMPT
# ══════════════════════════════════════════════════════════════════════════════

def prompt_folders() -> Tuple[Path, Path]:
    """
    Ask the user for input and output folder paths at runtime.
    Accepts absolute paths (C:\\Users\\...) or relative paths (./input).
    Re-prompts if the input folder does not exist.
    """
    print("\n" + "═" * 60)
    print("  AUTO TRANSLATION BATCH")
    print("═" * 60)

    # ── Input folder ──────────────────────────────────────────
    while True:
        raw = input("\n📂  Input folder (where your .txt / .csv files are):\n    > ").strip()
        if not raw:
            print("    ⚠  Path cannot be empty. Please try again.")
            continue
        input_folder = Path(raw)
        if not input_folder.exists():
            print(f"    ⚠  Folder not found: {input_folder.resolve()}")
            print("    Make sure the path is correct and try again.")
            continue
        if not input_folder.is_dir():
            print(f"    ⚠  That path is a file, not a folder. Please enter a folder path.")
            continue
        break

    # ── Output folder ─────────────────────────────────────────
    raw = input("\n📁  Output folder (where rough_L_1.csv etc. will be saved):\n    > ").strip()
    output_folder = Path(raw) if raw else input_folder / "output"
    print(f"\n    Output will be saved to: {output_folder.resolve()}")

    print("═" * 60 + "\n")
    return input_folder, output_folder

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING SETUP
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  DRIVER BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_driver() -> webdriver.Chrome:
    """
    Create a headless Chrome WebDriver suitable for running locally.
    webdriver-manager handles ChromeDriver download/version matching automatically.
    """
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    log.info("Chrome WebDriver started successfully.")
    return driver


# ══════════════════════════════════════════════════════════════════════════════
#  FILE PARSERS
# ══════════════════════════════════════════════════════════════════════════════

def parse_txt(filepath: Path) -> List[Tuple[str, str]]:
    """
    Parse a .txt file where each line is:  id, phrase
    Returns a list of (id, phrase) tuples.
    """
    phrases: List[Tuple[str, str]] = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", 1)
            if len(parts) == 2:
                phrases.append((parts[0].strip(), parts[1].strip()))
            else:
                # No comma → treat the whole line as a phrase, auto-number it
                phrases.append((str(len(phrases) + 1), line))
    return phrases


def parse_csv(filepath: Path) -> List[Tuple[str, str]]:
    """
    Parse a .csv file.

    Column auto-detection order:
      1. Headers containing 'english' or 'eng'  → phrase
      2. Headers containing 'id'               → id
      3. Fallback: column 0 = id, column 1 = phrase (headerless)
    """
    phrases: List[Tuple[str, str]] = []

    with open(filepath, encoding="utf-8") as f:
        reader = csv.reader(f)
        first_row = next(reader, None)

        if first_row is None:
            return phrases

        # Detect whether the first row is a header
        headers_lower = [h.strip().lower() for h in first_row]
        has_header = any(
            "english" in h or "eng" in h or "id" in h or "phrase" in h
            for h in headers_lower
        )

        if has_header:
            eng_idx = next(
                (i for i, h in enumerate(headers_lower) if "english" in h or "eng" in h),
                0,
            )
            id_idx = next(
                (i for i, h in enumerate(headers_lower) if h == "id" or h.endswith("_id")),
                None,
            )
            for row in reader:
                if len(row) > eng_idx:
                    phrase = row[eng_idx].strip()
                    num = row[id_idx].strip() if id_idx is not None and len(row) > id_idx else str(len(phrases) + 1)
                    if phrase:
                        phrases.append((num, phrase))
        else:
            # No header — treat first_row as data
            data_rows = [first_row] + list(reader)
            for row in data_rows:
                if len(row) >= 2:
                    phrases.append((row[0].strip(), row[1].strip()))
                elif len(row) == 1 and row[0].strip():
                    phrases.append((str(len(phrases) + 1), row[0].strip()))

    return phrases


def load_phrases(filepath: Path) -> List[Tuple[str, str]]:
    """
    Dispatch to the correct parser based on file extension.
    Returns a list of (id, phrase) tuples.
    """
    ext = filepath.suffix.lower()
    if ext == ".txt":
        return parse_txt(filepath)
    elif ext == ".csv":
        return parse_csv(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSLATOR
# ══════════════════════════════════════════════════════════════════════════════

def translate_phrase(
    driver: webdriver.Chrome,
    text: str,
    source_lang: str = SOURCE_LANG,
    target_lang: str = TARGET_LANG,
    retries: int = RETRY_COUNT,
    delay: float = DELAY,
) -> str:
    """
    Translate a single phrase using Google Translate via Selenium.

    Retries up to `retries` times if the result comes back blank.
    Returns the translated string, or "" if all retries are exhausted.
    """
    url = (
        f"https://translate.google.com/?hl=en&sl={source_lang}"
        f"&tl={target_lang}&text={urllib.parse.quote(text)}&op=translate"
    )

    for attempt in range(1, retries + 1):
        driver.get(url)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "span[jsname='W297wb']")
                )
            )
            elements = driver.find_elements(By.CSS_SELECTOR, "span[jsname='W297wb']")
            result = " ".join(el.text.strip() for el in elements if el.text.strip())
        except Exception:
            result = ""

        if result:
            time.sleep(delay)
            return result

        # Blank result → wait longer before retrying
        log.warning(f"  Blank result (attempt {attempt}/{retries}), retrying …")
        time.sleep(delay + 2)

    log.error(f"  Translation failed after {retries} retries for: {text[:60]!r}")
    return ""


# ══════════════════════════════════════════════════════════════════════════════
#  OUTPUT WRITER
# ══════════════════════════════════════════════════════════════════════════════

def save_results(
    results: List[dict],
    output_path: Path,
    target_column: str = TARGET_COLUMN,
) -> None:
    """Write results list to a CSV file at output_path."""
    fieldnames = ["id", "english", target_column]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


# ══════════════════════════════════════════════════════════════════════════════
#  SINGLE-FILE PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def process_file(
    driver: webdriver.Chrome,
    input_path: Path,
    output_path: Path,
) -> bool:
    """
    Translate all phrases in one input file and save the result.

    Returns True on success, False if the file could not be processed.
    """
    log.info(f"  Loading phrases from: {input_path.name}")

    try:
        phrases = load_phrases(input_path)
    except Exception as exc:
        log.error(f"  Failed to parse {input_path.name}: {exc}")
        return False

    if not phrases:
        log.warning(f"  No phrases found in {input_path.name} — skipping.")
        return False

    log.info(f"  Found {len(phrases)} phrase(s). Translating [{SOURCE_LANG} → {TARGET_LANG}] …")
    results: List[dict] = []

    for i, (num, phrase) in enumerate(phrases, 1):
        log.info(f"    [{i}/{len(phrases)}] {phrase[:70]!r} …")
        translation = translate_phrase(driver, phrase)
        log.info(f"           → {translation[:70]!r}")
        results.append({"id": num, "english": phrase, TARGET_COLUMN: translation})

        # Checkpoint save every SAVE_EVERY phrases
        if i % SAVE_EVERY == 0:
            save_results(results, output_path)
            log.info(f"  ✔ Progress checkpoint saved at {i}/{len(phrases)} phrases.")

    # Final save
    save_results(results, output_path)
    log.info(f"  ✔ Saved {len(results)} row(s) → {output_path}")
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  BATCH RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_batch() -> None:
    """
    Main entry point.

    1. Scans INPUT_FOLDER for supported files.
    2. Processes each file one at a time.
    3. Writes numbered output CSVs to OUTPUT_FOLDER.
    4. Logs a final summary.
    """
    input_folder, output_folder = prompt_folders()

    # Auto-create output folder
    output_folder.mkdir(parents=True, exist_ok=True)
    log.info(f"Output folder: {output_folder.resolve()}")

    # Discover input files (sorted for deterministic numbering)
    input_files = sorted(
        p for p in input_folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )

    if not input_files:
        log.warning(f"No supported files found in {input_folder.resolve()}")
        log.warning(f"Supported extensions: {', '.join(SUPPORTED_EXTS)}")
        return

    log.info(f"Found {len(input_files)} file(s) to process.\n")

    # Start WebDriver once — reuse across all files
    driver = build_driver()

    success_count = 0
    failure_count = 0

    try:
        for file_index, input_path in enumerate(input_files, start=1):
            output_filename = f"{OUTPUT_PREFIX}_{file_index}.csv"
            output_path     = output_folder / output_filename

            log.info("─" * 60)
            log.info(f"[{file_index}/{len(input_files)}]  Processing: {input_path.name}")
            log.info(f"  Output → {output_filename}")

            try:
                ok = process_file(driver, input_path, output_path)
                if ok:
                    success_count += 1
                    log.info(f"  ✅ Success: {input_path.name}")
                else:
                    failure_count += 1
                    log.warning(f"  ⚠ Skipped/failed: {input_path.name}")
            except Exception as exc:
                # One bad file must not stop the whole batch
                failure_count += 1
                log.error(f"  ❌ Unexpected error on {input_path.name}: {exc}", exc_info=True)

    finally:
        driver.quit()
        log.info("Chrome WebDriver closed.")

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("═" * 60)
    log.info("BATCH COMPLETE")
    log.info(f"  Total files  : {len(input_files)}")
    log.info(f"  ✅ Succeeded : {success_count}")
    log.info(f"  ❌ Failed    : {failure_count}")
    log.info(f"  Output folder: {output_folder.resolve()}")
    log.info("═" * 60)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_batch()
