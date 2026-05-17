"""
auto_translation_batch.py  —  RAM-optimised edition
─────────────────────────────────────────────────────────────────────────────
What changed for RAM:

  1. STREAMING PARSERS — parse_txt / parse_csv are now generators.
     They yield one (id, phrase) tuple at a time and never load the
     entire file into a list. A 100 000-row CSV uses the same memory
     as a 10-row one.

  2. DIRECT WRITE — process_file opens the output CSV once, writes each
     row immediately after translation, and flushes to disk.
     The old results[] list that kept every row in RAM is gone.

  3. CHROME MEMORY FLAGS — the browser is capped with:
       --js-flags=--max-old-space-size=128   (V8 heap <= 128 MB)
       --blink-settings=imagesEnabled=false  (no image decoding)
       --disk-cache-size=1                   (near-zero disk cache)
       --aggressive-cache-discard
     After every translation the driver loads about:blank to release
     the Google Translate DOM before the next request.

  4. GC BETWEEN FILES — gc.collect() runs after each file so Python
     reclaims any lingering string buffers promptly.

  5. RAM MONITOR — install psutil for live MB readings in the terminal:
       pip install psutil
     If psutil is not installed the script still works; RAM lines are
     simply skipped.

HOW TO RUN
─────────────────────────────────────────────────────────────────────────────
  pip install selenium webdriver-manager
  pip install psutil          # optional but recommended
  python auto_translation_batch.py

INPUT FILE FORMATS
─────────────────────────────────────────────────────────────────────────────
  .txt  ->  one phrase per line:  id, phrase text
  .csv  ->  with or without a header row; columns auto-detected
─────────────────────────────────────────────────────────────────────────────
"""

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import csv
import gc
import logging
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Iterator, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

OUTPUT_PREFIX  = "rough_L"      # rough_L_1.csv, rough_L_2.csv ...
SOURCE_LANG    = "en"
TARGET_LANG    = "hil"          # e.g. "fil", "es", "fr"
TARGET_COLUMN  = "hiligaynon"   # column name in output CSV

SUPPORTED_EXTS = {".txt", ".csv"}

DELAY          = 2.0            # seconds to wait after each successful translation
RETRY_COUNT    = 3              # retries on blank result
LOG_EVERY      = 10             # print RAM reading every N phrases

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  RAM MONITOR  (optional — needs psutil)
# ══════════════════════════════════════════════════════════════════════════════

try:
    import psutil as _psutil
    _PROC = _psutil.Process()

    def ram_mb() -> float:
        """Return current process RSS in MB."""
        return _PROC.memory_info().rss / 1_048_576

    def log_ram(label: str = "") -> None:
        log.info(f"  [RAM] {ram_mb():.1f} MB  {label}")

except ImportError:
    # psutil not installed — RAM logging silently skipped
    def ram_mb() -> float:
        return 0.0

    def log_ram(label: str = "") -> None:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  RUNTIME PATH PROMPT
# ══════════════════════════════════════════════════════════════════════════════

def prompt_folders() -> Tuple[Path, Path]:
    print("\n" + "=" * 60)
    print("  AUTO TRANSLATION BATCH  (RAM-optimised)")
    print("=" * 60)

    while True:
        raw = input("\n  Input folder (where your .txt / .csv files are):\n  > ").strip()
        if not raw:
            print("  Path cannot be empty.")
            continue
        folder = Path(raw)
        if not folder.exists():
            print(f"  Not found: {folder.resolve()}")
            continue
        if not folder.is_dir():
            print("  That is a file, not a folder.")
            continue
        break

    raw = input("\n  Output folder (where results will be saved):\n  > ").strip()
    out = Path(raw) if raw else folder / "output"
    print(f"\n  Output -> {out.resolve()}")
    print("=" * 60 + "\n")
    return folder, out


# ══════════════════════════════════════════════════════════════════════════════
#  CHROME DRIVER  (memory-constrained flags)
# ══════════════════════════════════════════════════════════════════════════════

def build_driver() -> webdriver.Chrome:
    """
    Start a headless Chrome with flags that keep its RAM footprint small.

    Key RAM flags:
      --js-flags=--max-old-space-size=128  caps V8 JavaScript heap at 128 MB
      --blink-settings=imagesEnabled=false skips image decoding entirely
      --disk-cache-size=1                  near-zero disk cache
      --aggressive-cache-discard           drops cached resources sooner
      --renderer-process-limit=1           one renderer process maximum
    """
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=900,600")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-blink-features=AutomationControlled")

    # ── RAM-saving flags ──────────────────────────────────────────────────────
    opts.add_argument("--js-flags=--max-old-space-size=128")
    opts.add_argument("--blink-settings=imagesEnabled=false")
    opts.add_argument("--disk-cache-size=1")
    opts.add_argument("--media-cache-size=1")
    opts.add_argument("--aggressive-cache-discard")
    opts.add_argument("--disable-application-cache")
    opts.add_argument("--renderer-process-limit=1")
    # ─────────────────────────────────────────────────────────────────────────

    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts,
    )
    log.info("Chrome WebDriver started.")
    log_ram("after driver start")
    return driver


# ══════════════════════════════════════════════════════════════════════════════
#  STREAMING FILE PARSERS
#  These are Python generators — they yield ONE row at a time.
#  No matter how large the file, only one line lives in memory at once.
# ══════════════════════════════════════════════════════════════════════════════

def stream_txt(filepath: Path) -> Iterator[Tuple[str, str]]:
    """
    Yield (id, phrase) from a .txt file one line at a time.
    Expected format per line:   id, phrase text
    If no comma found, the whole line becomes the phrase; id is auto-numbered.
    """
    auto_n = 0
    with open(filepath, encoding="utf-8") as fh:
        for line in fh:                     # reads ONE line — previous lines freed
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", 1)
            if len(parts) == 2:
                yield parts[0].strip(), parts[1].strip()
            else:
                auto_n += 1
                yield str(auto_n), line


def stream_csv(filepath: Path) -> Iterator[Tuple[str, str]]:
    """
    Yield (id, phrase) from a .csv file one row at a time.

    Column detection priority:
      1. Header containing 'english' or 'eng'  -> phrase column
      2. Header containing 'id'                -> id column
      3. No recognised header                  -> col 0 = id, col 1 = phrase
    """
    auto_n = 0

    with open(filepath, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        first_row = next(reader, None)
        if first_row is None:
            return

        headers_lower = [h.strip().lower() for h in first_row]
        has_header = any(
            kw in h
            for h in headers_lower
            for kw in ("english", "eng", "id", "phrase")
        )

        if has_header:
            eng_idx = next(
                (i for i, h in enumerate(headers_lower) if "english" in h or "eng" in h),
                0,
            )
            id_idx = next(
                (i for i, h in enumerate(headers_lower)
                 if h == "id" or h.endswith("_id")),
                None,
            )
            for row in reader:              # ONE row at a time — no list()
                if len(row) <= eng_idx:
                    continue
                phrase = row[eng_idx].strip()
                if not phrase:
                    continue
                auto_n += 1
                num = (
                    row[id_idx].strip()
                    if id_idx is not None and len(row) > id_idx
                    else str(auto_n)
                )
                yield num, phrase

        else:
            # First row is data, not a header — emit it then continue
            def _emit(row: list) -> Iterator[Tuple[str, str]]:
                nonlocal auto_n
                if len(row) >= 2 and row[1].strip():
                    yield row[0].strip(), row[1].strip()
                elif len(row) == 1 and row[0].strip():
                    auto_n += 1
                    yield str(auto_n), row[0].strip()

            yield from _emit(first_row)
            for row in reader:
                yield from _emit(row)


def stream_phrases(filepath: Path) -> Iterator[Tuple[str, str]]:
    """Dispatch to the correct streaming parser."""
    ext = filepath.suffix.lower()
    if ext == ".txt":
        yield from stream_txt(filepath)
    elif ext == ".csv":
        yield from stream_csv(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def count_phrases(filepath: Path) -> int:
    """
    Fast row count for progress display.
    Reads the file line-by-line but discards content immediately — only the
    counter integer is kept in memory.
    """
    ext = filepath.suffix.lower()
    n = 0
    with open(filepath, encoding="utf-8") as fh:
        if ext == ".txt":
            for line in fh:
                if line.strip():
                    n += 1
        elif ext == ".csv":
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                return 0
            headers_lower = [h.strip().lower() for h in header]
            has_header = any(
                kw in h
                for h in headers_lower
                for kw in ("english", "eng", "id", "phrase")
            )
            if not has_header:
                n = 1           # first row is data
            for _ in reader:    # count rows without storing them
                n += 1
    return n


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSLATOR
# ══════════════════════════════════════════════════════════════════════════════

def translate_phrase(
    driver: webdriver.Chrome,
    text: str,
    retries: int = RETRY_COUNT,
    delay: float = DELAY,
) -> str:
    """
    Translate one phrase via Google Translate.

    RAM note: after every page load (success or retry) the driver navigates
    to about:blank. This triggers Chrome's garbage collector on the renderer
    side, releasing the Google Translate DOM and JS objects before the next
    request loads.
    """
    url = (
        f"https://translate.google.com/?hl=en&sl={SOURCE_LANG}"
        f"&tl={TARGET_LANG}&text={urllib.parse.quote(text)}&op=translate"
    )

    result = ""
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

        # Navigate away immediately to free Chrome renderer RAM
        driver.get("about:blank")

        if result:
            time.sleep(delay)
            return result

        log.warning(f"  Blank result (attempt {attempt}/{retries}), retrying ...")
        time.sleep(delay + 2)

    log.error(f"  Failed after {retries} retries: {text[:60]!r}")
    return ""


# ══════════════════════════════════════════════════════════════════════════════
#  SINGLE-FILE PROCESSOR
#  Key change: NO results list. Each row is written to disk immediately.
# ══════════════════════════════════════════════════════════════════════════════

def process_file(
    driver: webdriver.Chrome,
    input_path: Path,
    output_path: Path,
) -> bool:
    """
    Stream phrases from input_path, translate each one, write directly to
    output_path row-by-row.

    Memory profile: at any moment only ONE phrase string and ONE translation
    string exist in Python memory. The output file on disk grows steadily
    while Python's heap stays flat.
    """
    try:
        total = count_phrases(input_path)
    except Exception as exc:
        log.error(f"  Could not count rows in {input_path.name}: {exc}")
        return False

    if total == 0:
        log.warning(f"  No phrases in {input_path.name} — skipping.")
        return False

    log.info(f"  {total} phrase(s). Translating [{SOURCE_LANG} -> {TARGET_LANG}] ...")
    log_ram("start of file")

    fieldnames = ["id", "english", TARGET_COLUMN]

    try:
        # Open output CSV ONCE — header first, then stream rows in
        with open(output_path, "w", newline="", encoding="utf-8") as out_fh:
            writer = csv.DictWriter(out_fh, fieldnames=fieldnames)
            writer.writeheader()

            for i, (num, phrase) in enumerate(stream_phrases(input_path), 1):
                log.info(f"    [{i}/{total}] {phrase[:70]!r} ...")
                translation = translate_phrase(driver, phrase)
                log.info(f"           -> {translation[:70]!r}")

                # Write row and flush to disk immediately
                # After this line, neither the phrase nor translation
                # string needs to stay in Python memory
                writer.writerow({
                    "id": num,
                    "english": phrase,
                    TARGET_COLUMN: translation,
                })
                out_fh.flush()

                # Periodic RAM check (only if psutil installed)
                if i % LOG_EVERY == 0:
                    log_ram(f"phrase {i}/{total}")

    except Exception as exc:
        log.error(f"  Error during processing: {exc}", exc_info=True)
        return False

    log.info(f"  Wrote {total} row(s) -> {output_path.name}")
    log_ram("end of file")
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  BATCH RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_batch() -> None:
    input_folder, output_folder = prompt_folders()
    output_folder.mkdir(parents=True, exist_ok=True)

    input_files = sorted(
        p for p in input_folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )

    if not input_files:
        log.warning(f"No supported files in {input_folder.resolve()}")
        log.warning(f"Supported: {', '.join(SUPPORTED_EXTS)}")
        return

    log.info(f"Found {len(input_files)} file(s) to process.")
    log_ram("before driver start")

    driver = build_driver()
    success_count = 0
    failure_count = 0

    try:
        for idx, input_path in enumerate(input_files, start=1):
            output_filename = f"{OUTPUT_PREFIX}_{idx}.csv"
            output_path     = output_folder / output_filename

            log.info("-" * 60)
            log.info(f"[{idx}/{len(input_files)}]  {input_path.name}  ->  {output_filename}")

            try:
                ok = process_file(driver, input_path, output_path)
                if ok:
                    success_count += 1
                    log.info(f"  OK: {input_path.name}")
                else:
                    failure_count += 1
                    log.warning(f"  Skipped: {input_path.name}")
            except Exception as exc:
                failure_count += 1
                log.error(f"  Error on {input_path.name}: {exc}", exc_info=True)

            # Prompt Python's GC to reclaim any lingering buffers between files
            gc.collect()
            log_ram(f"after file {idx}")

    finally:
        driver.quit()
        log.info("Chrome closed.")
        gc.collect()
        log_ram("final")

    log.info("=" * 60)
    log.info("BATCH COMPLETE")
    log.info(f"  Total   : {len(input_files)}")
    log.info(f"  OK      : {success_count}")
    log.info(f"  Failed  : {failure_count}")
    log.info(f"  Output  : {output_folder.resolve()}")
    log.info("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_batch()