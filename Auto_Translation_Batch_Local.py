# =============================================================================
#  auto_translation_batch.py
#  RAM-optimised + Pause/Resume Edition  v3
#  Language: Python 3.8+
# =============================================================================
#
# WHAT THIS SCRIPT DOES
# ─────────────────────
#   Reads one or more .txt or .csv files containing English phrases, sends
#   each phrase to Google Translate via a headless Chrome browser, and saves
#   the translations to new CSV files inside an output folder you choose.
#
#   It is designed to handle large datasets (1 000 – 100 000+ rows) without
#   running out of RAM, and it can be safely paused and resumed at any time.
#
# =============================================================================
#  QUICK-START  (first time setup)
# =============================================================================
#
#   STEP 1 — Install Python 3.8 or newer
#     Download from https://www.python.org/downloads/
#     During installation, tick "Add Python to PATH".
#
#   STEP 2 — Install Google Chrome
#     Download from https://www.google.com/chrome/
#     The script controls Chrome automatically; you do not open it yourself.
#
#   STEP 3 — Install required Python libraries
#     Open a terminal (Command Prompt on Windows, Terminal on Mac/Linux) and
#     run these two commands:
#
#       pip install selenium webdriver-manager
#       pip install psutil
#
#     selenium         — controls the Chrome browser from Python
#     webdriver-manager— automatically downloads the matching ChromeDriver
#     psutil           — shows live RAM usage in the terminal (optional but
#                        recommended so you can monitor memory)
#
#   STEP 4 — Prepare your input files
#     Place all your .txt or .csv phrase files in one folder.
#     See "INPUT FILE FORMATS" below for the exact format.
#
#   STEP 5 — Run the script
#     In your terminal, navigate to the folder where this file is saved:
#
#       cd C:\Users\YourName\Downloads        (Windows example)
#       cd /home/yourname/Downloads           (Linux/Mac example)
#
#     Then run:
#
#       python auto_translation_batch.py
#
#     The script will ask you two questions:
#       1. Input folder  — where your .txt / .csv phrase files are
#       2. Output folder — where you want the translated CSV files saved
#                          (press Enter to use a subfolder called "output"
#                           inside your input folder)
#
#     STEP 6 — Install 1.1.1.1  
#       You need it so that google translate wont block you IP
#
# =============================================================================
#  INPUT FILE FORMATS
# =============================================================================
#
#   --- FORMAT A: Plain text file (.txt) ---
#   One phrase per line. Each line should be: id, phrase text
#   Example:
#     1, Hello, how are you?
#     2, Good morning everyone
#     3, Where is the nearest hospital?
#
#   If a line has no comma, the whole line is used as the phrase and the
#   script auto-numbers it.
#
#   --- FORMAT B: CSV file (.csv) ---
#   The script auto-detects whether your CSV has a header row.
#
#   With header (recommended):
#     id,english
#     1,Hello how are you
#     2,Good morning everyone
#
#   The header must contain the word "english" or "eng" for the phrase column
#   and "id" for the ID column. Other column names are ignored.
#
#   Without header:
#     1,Hello how are you
#     2,Good morning everyone
#   The script assumes column 0 = id, column 1 = phrase.
#
# =============================================================================
#  OUTPUT FILES
# =============================================================================
#
#   For each input file the script creates one output CSV named:
#     rough_L_1.csv   (for your 1st input file)
#     rough_L_2.csv   (for your 2nd input file)
#     ... and so on
#
#   Each output CSV has three columns:
#     id          — the original phrase ID
#     english     — the original English phrase
#     hiligaynon  — the translated text  (column name set by TARGET_COLUMN)
#
#   Example output row:
#     1, Hello how are you, Kamusta ka
#
#   You can change the output prefix and column name in the CONFIG section
#   below (OUTPUT_PREFIX and TARGET_COLUMN).
#
# =============================================================================
#  PAUSE AND RESUME
# =============================================================================
#
#   PAUSING:
#     Press Ctrl+C at any time while the script is running.
#     The script will finish translating the phrase it is currently on,
#     save a checkpoint file, close Chrome cleanly, then stop.
#     You will not lose any work already done.
#
#   RESUMING:
#     Simply run the script again with the same output folder.
#     It will find the checkpoint and ask:
#
#       [R] Resume   [N] New run — choose:
#
#     Press R and Enter to continue from where you left off.
#     Press N and Enter to delete the checkpoint and start over from scratch.
#
#   WHAT THE CHECKPOINT SAVES:
#     - Which file in the batch was being processed
#     - How many rows of that file were already translated and written
#     - The ID of the last written row
#     - The timestamp of the last save
#
#   CRASH / POWER CUT:
#     The checkpoint is written to disk every CHECKPOINT_EVERY rows AND
#     right before every Chrome restart, so in the worst case you only
#     lose CHECKPOINT_EVERY rows (default: 10) on a sudden crash.
#
#   CHECKPOINT FILE LOCATION:
#     <your output folder>/translation_checkpoint.json
#     You can open this file in any text editor to inspect the saved state.
#     Do not edit it manually unless you know what you are doing.
#
#   EXISTING OUTPUT CSV ON RESUME:
#     When resuming a partially translated file, the script opens the
#     existing rough_L_N.csv in APPEND mode. It fast-forwards past the
#     already-translated rows and continues writing new rows to the same
#     file. No data is overwritten and no duplicate header is written.
#
# =============================================================================
#  RAM / MEMORY MANAGEMENT
# =============================================================================
#
#   This script is designed to stay memory-efficient even over very long runs.
#   Key strategies:
#
#   1. Chrome is restarted every CHROME_RESTART_EVERY phrases (default 100).
#      Chrome leaks memory slowly over hundreds of page loads. Restarting it
#      completely kills the old process and starts a clean one, so RAM stays
#      flat instead of climbing over time. A checkpoint is force-saved before
#      each restart so a crash during restart loses zero rows.
#
#   2. Input files are read one line at a time (streaming / generator).
#      A 100 000-row CSV uses the same Python memory as a 10-row one.
#
#   3. Each translated row is written to disk immediately and flushed.
#      There is no in-memory list that grows as the script runs.
#
#   4. The phrase string and translation string are explicitly deleted
#      (del phrase, del translation) right after each row is written,
#      so Python's memory allocator can reuse that space immediately.
#
#   5. Python's garbage collector (gc.collect) is called every GC_EVERY
#      phrases to reclaim memory promptly inside a long file.
#
# =============================================================================
#  CHANGING THE TARGET LANGUAGE
# =============================================================================
#
#   Find the CONFIG section below and change TARGET_LANG to any Google
#   Translate language code. Examples:
#
#     TARGET_LANG = "hil"   <- Hiligaynon  (default)
#     TARGET_LANG = "fil"   <- Filipino / Tagalog
#     TARGET_LANG = "ceb"   <- Cebuano
#     TARGET_LANG = "es"    <- Spanish
#     TARGET_LANG = "ja"    <- Japanese
#     TARGET_LANG = "zh-CN" <- Chinese Simplified
#
#   Also update TARGET_COLUMN to match, e.g. TARGET_COLUMN = "tagalog"
#   so the output CSV column has the right name.
#
# =============================================================================
#  TUNING FOR YOUR MACHINE
# =============================================================================
#
#   All tunable values are in the CONFIG section. Key ones for performance:
#
#   CHROME_RESTART_EVERY (default 100)
#     How many phrases to translate before restarting Chrome.
#     Lower value = less RAM but slightly more overhead per restart.
#     Raise to 150-200 if your machine has plenty of RAM.
#     Lower to 50 if you are on a very low-RAM machine (< 4 GB).
#
#   CHECKPOINT_EVERY (default 10)
#     How often to write the checkpoint to disk.
#     Lower value = safer against crashes, slightly more disk I/O.
#     Setting it to 1 saves after every single row (maximum safety).
#
#   DELAY (default 2.0 seconds)
#     How long to wait after each successful translation before the next.
#     Too low and Google Translate may start blocking requests.
#     Increase to 3.0–5.0 if you see many blank/failed translations.
#
#   RETRY_COUNT (default 3)
#     How many times to retry a phrase that returns a blank result.
#
# =============================================================================
#  TROUBLESHOOTING
# =============================================================================
#
#   "ChromeDriver not found" or version mismatch error
#     The webdriver-manager library handles this automatically. Make sure
#     you have an internet connection on first run so it can download the
#     correct ChromeDriver version for your Chrome.
#
#   Many blank / empty translations
#     Google Translate may be rate-limiting you. Try:
#       - Increasing DELAY to 4.0 or 5.0
#       - Decreasing CHROME_RESTART_EVERY to restart Chrome more often
#       - Running fewer phrases at a time
#
#   Script crashes immediately on startup
#     Make sure you ran:  pip install selenium webdriver-manager
#     Make sure Google Chrome is installed on your computer.
#
#   Output CSV has duplicate rows after a resume
#     This should not happen with the current code. If it does, it means
#     the checkpoint file was corrupted. Open translation_checkpoint.json,
#     check the rows_done value, manually delete the extra rows from the CSV
#     using Excel or a text editor, set rows_done to the correct count, then
#     resume again.
#
#   "No supported files" warning
#     Make sure your input files end in .txt or .csv (lowercase).
#     Hidden files and folders are ignored automatically.
#
# =============================================================================

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import csv          # reading and writing CSV files
import gc           # Python garbage collector — called manually for RAM control
import itertools    # itertools.islice used for memory-efficient fast-forward on resume
import json         # reading and writing the checkpoint file
import logging      # structured log output to the terminal
import sys          # access to stdout for the log handler
import time         # time.sleep() between translations to avoid rate limiting
import urllib.parse # URL-encoding phrases before passing them to Google Translate
from datetime import datetime   # timestamp saved inside the checkpoint
from pathlib import Path        # cross-platform file and folder path handling
from typing import Iterator, Optional, Tuple  # type hints for readability

# Selenium — controls the headless Chrome browser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# webdriver-manager — automatically downloads the correct ChromeDriver binary
from webdriver_manager.chrome import ChromeDriverManager


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG  —  edit these values to customise the script's behaviour
# ══════════════════════════════════════════════════════════════════════════════

# Prefix for output filenames.
# With OUTPUT_PREFIX = "rough_L", output files are named:
#   rough_L_1.csv, rough_L_2.csv, rough_L_3.csv ...
OUTPUT_PREFIX        = "rough_L"

# Language code for the source text.
# "en" means the input phrases are in English.
SOURCE_LANG          = "en"

# Language code for the translation target.
# Change this to translate into a different language:
#   "hil" = Hiligaynon, "fil" = Filipino, "ceb" = Cebuano,
#   "es"  = Spanish,    "ja"  = Japanese, "fr"  = French
TARGET_LANG          = "hil"

# Name of the translation column in the output CSV.
# Update this to match TARGET_LANG so the column header makes sense.
TARGET_COLUMN        = "hiligaynon"

# File extensions the script will look for in the input folder.
# Only files with these extensions are processed; everything else is ignored.
SUPPORTED_EXTS       = {".txt", ".csv"}

# Filename of the checkpoint saved inside the output folder.
# You can open this in any text editor to inspect or verify the saved state.
CHECKPOINT_FILE      = "translation_checkpoint.json"

# Seconds to wait after each successful translation before starting the next.
# Increase this (e.g. 3.0 or 5.0) if Google Translate starts returning
# blank results, which is a sign of rate-limiting.
DELAY                = 2.0

# How many times to retry a phrase that returned a blank translation.
# After RETRY_COUNT failed attempts the row is written with an empty
# translation and the script moves on.
RETRY_COUNT          = 3

# ── RAM tuning ────────────────────────────────────────────────────────────────

# Restart Chrome completely every N translated phrases.
# This is the most important RAM control: Chrome leaks renderer heap memory
# over hundreds of page loads and never fully frees it on its own.
# Killing and restarting the process resets it to a clean baseline.
#   Recommended range: 50 – 150
#   Lower = less RAM usage, slightly more time lost on restarts
#   Higher = faster overall but RAM climbs more between restarts
CHROME_RESTART_EVERY = 100

# Write the checkpoint JSON to disk every N rows.
# A checkpoint is ALSO force-written before every Chrome restart, so in the
# worst case (plain crash between normal checkpoints) you lose at most
# CHECKPOINT_EVERY rows of work.
#   Set to 1 for maximum crash safety (one extra disk write per row).
#   Set to 25–50 if disk I/O is a concern on your machine.
CHECKPOINT_EVERY     = 10

# Call Python's garbage collector (gc.collect) every N phrases inside the
# main loop. This reclaims string buffers and other objects promptly without
# waiting for Python's automatic GC threshold to trigger.
GC_EVERY             = 25

# Print a RAM usage reading every N phrases.
# Only visible if psutil is installed (pip install psutil).
# Set to 0 to disable mid-loop RAM logging.
LOG_EVERY            = 50

# ─────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING SETUP
#  Configures terminal output with timestamps and log levels.
#  You do not need to change anything here.
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  RAM MONITOR
#  Uses the psutil library to show live memory usage in the terminal.
#  If psutil is not installed the functions below do nothing — the script
#  still works normally, just without RAM readings.
#  Install with:  pip install psutil
# ══════════════════════════════════════════════════════════════════════════════

try:
    import psutil as _psutil # type: ignore
    _PROC = _psutil.Process()   # represents this running Python process

    def ram_mb() -> float:
        """Return current process RAM usage in megabytes (RSS)."""
        return _PROC.memory_info().rss / 1_048_576

    def log_ram(label: str = "") -> None:
        """Print a RAM reading to the terminal at INFO level."""
        log.info(f"  [RAM] {ram_mb():.1f} MB  {label}")

except ImportError:
    # psutil not installed — define silent no-op versions so the rest of
    # the code can call log_ram() freely without checking every time.
    def ram_mb() -> float:
        return 0.0

    def log_ram(label: str = "") -> None:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  CHROME DRIVER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def build_driver() -> webdriver.Chrome:
    """
    Start a new headless Chrome browser session with RAM-saving flags.

    'Headless' means Chrome runs invisibly in the background with no
    visible window. All the flags passed here tell Chrome to use as
    little memory as possible.

    Called once at startup and again after every CHROME_RESTART_EVERY
    phrases to reset Chrome's leaked renderer heap.
    """
    opts = Options()

    # Run Chrome with no visible window
    opts.add_argument("--headless=new")

    # Required on Linux servers / WSL to run without a display
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    # Skip GPU rendering — not needed for text scraping
    opts.add_argument("--disable-gpu")

    # Small window is enough; reduces Chrome's render surface
    opts.add_argument("--window-size=900,600")

    # Disable extensions and default apps to reduce startup overhead
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--no-first-run")

    # Hide Selenium's automation fingerprint (prevents some bot detection)
    opts.add_argument("--disable-blink-features=AutomationControlled")

    # ── RAM-saving flags ──────────────────────────────────────────────────────

    # Cap Chrome's JavaScript (V8) heap at 128 MB.
    # Without this flag, V8 can grow its heap to several hundred MB.
    opts.add_argument("--js-flags=--max-old-space-size=128")

    # Skip image decoding entirely — we only need text from the page.
    opts.add_argument("--blink-settings=imagesEnabled=false")

    # Set disk and media cache to near-zero to stop Chrome writing
    # hundreds of MB of cached assets to disk.
    opts.add_argument("--disk-cache-size=1")
    opts.add_argument("--media-cache-size=1")

    # Tell Chrome to drop cached resources aggressively
    opts.add_argument("--aggressive-cache-discard")
    opts.add_argument("--disable-application-cache")

    # Allow only one renderer process — the default can spin up several
    opts.add_argument("--renderer-process-limit=1")

    # Stop Chrome from making background network requests (update checks etc.)
    opts.add_argument("--disable-background-networking")

    # Disable Chrome account sync (not needed here, adds overhead)
    opts.add_argument("--disable-sync")

    # ─────────────────────────────────────────────────────────────────────────

    # Remove the "Chrome is being controlled by automated software" banner
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    # webdriver-manager downloads the ChromeDriver binary that matches your
    # installed Chrome version automatically — no manual download needed.
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts,
    )

    log.info("  Chrome WebDriver started.")
    log_ram("after driver start")
    return driver


def restart_driver(old_driver: webdriver.Chrome) -> webdriver.Chrome:
    """
    Completely shut down the current Chrome process and start a fresh one.

    This is the primary RAM-recovery mechanism in the script.
    Chrome's renderer process leaks heap memory over long runs — even with
    about:blank navigation between requests, some objects accumulate and
    are never freed. The only reliable fix is to kill the process entirely.

    A checkpoint is always force-saved before this function is called,
    so a crash during restart loses zero rows of translated data.
    """
    log.info("  [Chrome restart] Closing old driver ...")
    log_ram("before Chrome restart")

    try:
        old_driver.quit()   # sends SIGTERM to the Chrome process
    except Exception:
        pass                # ignore errors if Chrome already died

    gc.collect()            # reclaim Python-side Selenium objects
    new_driver = build_driver()
    log_ram("after Chrome restart")
    return new_driver


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKPOINT  (pause / resume state)
#
#  The checkpoint is a small JSON file stored in your output folder.
#  It records exactly where the script stopped so it can continue from
#  the same point on the next run.
#
#  Sample checkpoint file contents:
#  {
#    "input_folder":  "C:/Users/Josh/phrases",
#    "output_folder": "C:/Users/Josh/phrases/output",
#    "file_index":    2,        <- currently on the 2nd input file
#    "rows_done":     450,      <- 450 rows already written in that file
#    "last_id":       "450",    <- ID of the last successfully written row
#    "timestamp":     "2025-05-15T14:32:01"
#  }
# ══════════════════════════════════════════════════════════════════════════════

def checkpoint_path(output_folder: Path) -> Path:
    """Return the full path of the checkpoint JSON file."""
    return output_folder / CHECKPOINT_FILE


def save_checkpoint(
    output_folder: Path,
    input_folder: Path,
    file_index: int,
    rows_done: int,
    last_id: str = "",
) -> None:
    """
    Write current progress to disk atomically.

    Uses a write-to-temp-then-rename strategy: the JSON is written to a
    .tmp file first, then renamed to the real checkpoint file.
    This means a hard crash or power cut mid-write cannot corrupt the
    checkpoint — the rename is atomic on both Windows and Linux.
    """
    data = {
        "input_folder":  str(input_folder.resolve()),
        "output_folder": str(output_folder.resolve()),
        "file_index":    file_index,    # which input file (1-based)
        "rows_done":     rows_done,     # rows written in that file so far
        "last_id":       last_id,       # ID of the last written row
        "timestamp":     datetime.now().isoformat(timespec="seconds"),
    }
    cp  = checkpoint_path(output_folder)
    tmp = cp.with_suffix(".tmp")        # write here first
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(cp)                     # atomic rename to final checkpoint path


def load_checkpoint(output_folder: Path) -> Optional[dict]:
    """
    Read and return the checkpoint dict if it exists, otherwise return None.
    Returns None if the file is missing or cannot be parsed.
    """
    cp = checkpoint_path(output_folder)
    if not cp.exists():
        return None
    try:
        return json.loads(cp.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning(f"Could not read checkpoint: {exc}")
        return None


def delete_checkpoint(output_folder: Path) -> None:
    """
    Delete the checkpoint file after the full batch completes, or when the
    user chooses to start a new run from scratch.
    """
    cp = checkpoint_path(output_folder)
    if cp.exists():
        cp.unlink()
        log.info("  Checkpoint deleted — batch fully complete.")


# ══════════════════════════════════════════════════════════════════════════════
#  RUNTIME PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def prompt_folders() -> Tuple[Path, Path]:
    """
    Ask the user for the input folder and output folder at startup.

    Input folder  — must already exist and contain at least one .txt or .csv file.
    Output folder — created automatically if it does not exist.
                    Defaults to a subfolder called "output" inside the input folder
                    if the user just presses Enter.
    """
    print("\n" + "=" * 60)
    print("  AUTO TRANSLATION BATCH  (RAM-optimised + Resume)  v3")
    print("=" * 60)

    # Keep asking until a valid existing directory is entered
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

    # Output folder — blank input uses the default subfolder
    raw = input("\n  Output folder (where results will be saved):\n  > ").strip()
    out = Path(raw) if raw else folder / "output"
    print(f"\n  Output -> {out.resolve()}")
    print("=" * 60 + "\n")
    return folder, out


def prompt_resume(checkpoint: dict) -> bool:
    """
    Display the saved checkpoint details and ask whether to resume or restart.

    Returns True  — user chose to resume from the checkpoint.
    Returns False — user chose to start a new run (checkpoint will be deleted).
    """
    print("\n" + "=" * 60)
    print("  CHECKPOINT FOUND — a previous run was paused or interrupted.")
    print("=" * 60)
    print(f"  Saved at  : {checkpoint.get('timestamp', 'unknown')}")
    print(f"  File #    : {checkpoint['file_index']}")
    print(f"  Rows done : {checkpoint['rows_done']}"
          f"  (last id: {checkpoint.get('last_id', '?')})")
    print()
    print("  [R] Resume  — continue from where it stopped")
    print("  [N] New run — delete checkpoint and start over")
    print()

    while True:
        choice = input("  Your choice: ").strip().upper()
        if choice == "R":
            return True
        if choice == "N":
            return False
        print("  Please enter R or N.")


# ══════════════════════════════════════════════════════════════════════════════
#  STREAMING FILE PARSERS
#
#  These functions are Python generators — they use the 'yield' keyword to
#  produce one (id, phrase) pair at a time instead of loading the entire
#  file into a list.
#
#  Memory profile: at any moment only one line of the file exists in RAM.
#  A 100 000-row CSV uses the same Python memory as a 10-row one.
# ══════════════════════════════════════════════════════════════════════════════

def stream_txt(filepath: Path) -> Iterator[Tuple[str, str]]:
    """
    Yield (id, phrase) pairs from a plain text file one line at a time.

    Expected line format:  id, phrase text
    Example:               1, Hello how are you?

    If a line contains no comma, the whole line becomes the phrase and
    the script assigns an auto-incrementing number as the ID.
    Blank lines are skipped automatically.
    """
    auto_n = 0
    with open(filepath, encoding="utf-8") as fh:
        for line in fh:                     # Python reads one line at a time
            line = line.strip()
            if not line:
                continue                    # skip blank lines
            parts = line.split(",", 1)      # split on first comma only
            if len(parts) == 2:
                yield parts[0].strip(), parts[1].strip()
            else:
                auto_n += 1
                yield str(auto_n), line     # no comma — use whole line as phrase


def stream_csv(filepath: Path) -> Iterator[Tuple[str, str]]:
    """
    Yield (id, phrase) pairs from a CSV file one row at a time.

    Column detection rules (applied automatically):
      - If the first row contains "english" or "eng" -> that column is the phrase
      - If the first row contains "id" or ends with "_id" -> that column is the ID
      - If no recognised header is found -> column 0 = id, column 1 = phrase

    Rows with an empty phrase column are skipped automatically.
    """
    auto_n = 0
    with open(filepath, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        first_row = next(reader, None)      # read only the first row
        if first_row is None:
            return                          # empty file — nothing to yield

        headers_lower = [h.strip().lower() for h in first_row]

        # Determine whether the first row is a header or a data row
        has_header = any(
            kw in h
            for h in headers_lower
            for kw in ("english", "eng", "id", "phrase")
        )

        if has_header:
            # Find which column index holds the phrase and the ID
            eng_idx = next(
                (i for i, h in enumerate(headers_lower)
                 if "english" in h or "eng" in h),
                0,                          # default to first column
            )
            id_idx = next(
                (i for i, h in enumerate(headers_lower)
                 if h == "id" or h.endswith("_id")),
                None,                       # None means auto-number
            )
            for row in reader:              # one row at a time — no list()
                if len(row) <= eng_idx:
                    continue
                phrase = row[eng_idx].strip()
                if not phrase:
                    continue                # skip rows with empty phrase
                auto_n += 1
                num = (
                    row[id_idx].strip()
                    if id_idx is not None and len(row) > id_idx
                    else str(auto_n)
                )
                yield num, phrase

        else:
            # No recognised header — first row is data
            def _emit(row: list) -> Iterator[Tuple[str, str]]:
                nonlocal auto_n
                if len(row) >= 2 and row[1].strip():
                    yield row[0].strip(), row[1].strip()
                elif len(row) == 1 and row[0].strip():
                    auto_n += 1
                    yield str(auto_n), row[0].strip()

            yield from _emit(first_row)     # emit the first data row
            for row in reader:
                yield from _emit(row)


def stream_phrases(filepath: Path) -> Iterator[Tuple[str, str]]:
    """
    Dispatch to the correct streaming parser based on file extension.
    This is the single entry point used by process_file — it never matters
    to the rest of the code whether the input was .txt or .csv.
    """
    ext = filepath.suffix.lower()
    if ext == ".txt":
        yield from stream_txt(filepath)
    elif ext == ".csv":
        yield from stream_csv(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def count_phrases(filepath: Path) -> int:
    """
    Count the total number of phrases in a file for the progress display.

    Reads line-by-line and discards content immediately — only an integer
    counter is kept in memory regardless of file size.
    Called once per file before translation starts.
    """
    ext = filepath.suffix.lower()
    n   = 0
    with open(filepath, encoding="utf-8") as fh:
        if ext == ".txt":
            for line in fh:
                if line.strip():
                    n += 1
        elif ext == ".csv":
            reader     = csv.reader(fh)
            header     = next(reader, None)
            if header is None:
                return 0
            headers_lower = [h.strip().lower() for h in header]
            has_header = any(
                kw in h
                for h in headers_lower
                for kw in ("english", "eng", "id", "phrase")
            )
            if not has_header:
                n = 1           # first row is data, not a header
            for _ in reader:    # count without storing rows
                n += 1
    return n


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSLATOR
#
#  Sends one phrase to Google Translate and returns the translated text.
#  Uses the actual Google Translate website (not the paid API), controlled
#  via the headless Chrome browser.
# ══════════════════════════════════════════════════════════════════════════════

def translate_phrase(
    driver: webdriver.Chrome,
    text: str,
    retries: int = RETRY_COUNT,
    delay: float = DELAY,
) -> str:
    """
    Translate a single phrase and return the result as a string.

    How it works:
      1. Builds a Google Translate URL with the phrase URL-encoded
      2. Loads the URL in headless Chrome
      3. Waits for the translation element to appear on the page
      4. Reads the translated text from the element
      5. Navigates to about:blank to release the page from Chrome's memory
      6. Returns the translation (or retries if the result is blank)

    If all retries are exhausted, returns an empty string.
    The row will still be written to the output CSV with an empty
    translation column so no rows are skipped or lost.
    """
    # Build the translation URL — urllib.parse.quote makes the phrase
    # safe to embed in a URL (handles spaces, punctuation, etc.)
    url = (
        f"https://translate.google.com/?hl=en&sl={SOURCE_LANG}"
        f"&tl={TARGET_LANG}&text={urllib.parse.quote(text)}&op=translate"
    )

    result = ""
    for attempt in range(1, retries + 1):
        driver.get(url)

        try:
            # Wait up to 10 seconds for the translation span to appear.
            # jsname='W297wb' is the internal attribute Google uses for the
            # translated text spans. If this selector stops working it may
            # mean Google changed their page structure.
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "span[jsname='W297wb']")
                )
            )
            elements = driver.find_elements(By.CSS_SELECTOR, "span[jsname='W297wb']")

            # Join multiple spans (long phrases may be split across several)
            result = " ".join(el.text.strip() for el in elements if el.text.strip())

            # Free the list of Selenium element objects immediately —
            # they hold references into Chrome's DOM which costs memory
            del elements

        except Exception:
            result = ""     # timeout or element not found

        # Navigate to about:blank after every attempt.
        # This tells Chrome's renderer to discard the Google Translate DOM
        # and all its associated JS objects, freeing renderer heap memory
        # before the next request is loaded.
        driver.get("about:blank")

        if result:
            time.sleep(delay)   # polite delay to avoid rate limiting
            return result

        log.warning(f"  Blank result (attempt {attempt}/{retries}), retrying ...")
        time.sleep(delay + 2)   # longer wait before retry

    log.error(f"  Failed after {retries} retries: {text[:60]!r}")
    return ""   # empty string — caller will write an empty cell to the CSV


# ══════════════════════════════════════════════════════════════════════════════
#  SINGLE-FILE PROCESSOR
#
#  This is the core function. It:
#    1. Opens the output CSV (fresh or append depending on resume state)
#    2. Fast-forwards through already-done rows (on resume)
#    3. Translates each remaining phrase
#    4. Writes and flushes each row immediately
#    5. Saves the checkpoint and calls GC on schedule
#    6. Restarts Chrome on schedule
#    7. Handles Ctrl+C cleanly at any point
# ══════════════════════════════════════════════════════════════════════════════

def process_file(
    driver: webdriver.Chrome,
    input_path: Path,
    output_path: Path,
    output_folder: Path,
    input_folder: Path,
    file_index: int,
    skip_rows: int = 0,
    append_mode: bool = False,
) -> Tuple[bool, bool, webdriver.Chrome]:
    """
    Translate all phrases in input_path and write results to output_path.

    Parameters
    ----------
    driver        : active Chrome WebDriver instance
    input_path    : path to the source .txt or .csv file
    output_path   : path to the output CSV to write (or append to)
    output_folder : folder containing the checkpoint file
    input_folder  : original input folder (saved in the checkpoint)
    file_index    : 1-based position of this file in the batch
    skip_rows     : number of rows already completed in a previous run.
                    These are fast-forwarded past WITHOUT calling the
                    translator — they are already in the output CSV.
    append_mode   : if True, the output CSV is opened in append mode
                    (no header written, new rows added to the end).
                    Set to True when resuming a partially done file.

    Returns
    -------
    (completed, paused, driver)
      completed : True if every row in the file was translated successfully
      paused    : True if the user pressed Ctrl+C mid-file
      driver    : the Chrome driver instance (may be a new object if
                  Chrome was restarted one or more times during this file)
    """
    # Count total rows first so we can show accurate progress like [45/1000]
    try:
        total = count_phrases(input_path)
    except Exception as exc:
        log.error(f"  Could not count rows in {input_path.name}: {exc}")
        return False, False, driver

    if total == 0:
        log.warning(f"  No phrases found in {input_path.name} — skipping.")
        return False, False, driver

    if skip_rows > 0:
        log.info(f"  Resuming at row {skip_rows + 1} / {total}  "
                 f"({skip_rows} rows already translated)")
    else:
        log.info(f"  {total} phrase(s) to translate  [{SOURCE_LANG} -> {TARGET_LANG}]")

    log_ram("start of file")

    fieldnames = ["id", "english", TARGET_COLUMN]

    # "a" = append mode (resume), "w" = write mode (fresh start)
    file_mode  = "a" if append_mode else "w"

    # rows_done tracks total rows written to THIS file across all runs
    rows_done  = skip_rows

    try:
        with open(output_path, file_mode, newline="", encoding="utf-8") as out_fh:
            writer = csv.DictWriter(out_fh, fieldnames=fieldnames)

            # Only write the header on a fresh file, never on append
            if not append_mode:
                writer.writeheader()

            phrase_iter = stream_phrases(input_path)

            # ── Fast-forward on resume ────────────────────────────────────────
            # Use itertools.islice to consume exactly skip_rows items from the
            # generator without building any intermediate list.
            # Memory cost: O(1) regardless of how many rows we are skipping.
            # No translation is called during this step.
            if skip_rows:
                for _ in itertools.islice(phrase_iter, skip_rows):
                    pass    # discard — these rows are already in the output CSV

            # ── Main translation loop ─────────────────────────────────────────
            for i, (num, phrase) in enumerate(phrase_iter, start=skip_rows + 1):
                log.info(f"    [{i}/{total}]  {phrase[:70]!r} ...")

                try:
                    translation = translate_phrase(driver, phrase)
                except KeyboardInterrupt:
                    # Ctrl+C pressed while inside translate_phrase.
                    # Save checkpoint immediately and exit cleanly.
                    log.warning("\n  Ctrl+C detected. Saving checkpoint ...")
                    save_checkpoint(output_folder, input_folder,
                                    file_index, rows_done, num)
                    return False, True, driver

                log.info(f"           -> {translation[:70]!r}")

                # Write the row and flush to disk immediately.
                # No data is kept in memory — the OS writes it to the file.
                writer.writerow({
                    "id":          num,
                    "english":     phrase,
                    TARGET_COLUMN: translation,
                })
                out_fh.flush()      # ensure the row is on disk, not in a buffer
                rows_done += 1

                # Explicitly delete the two largest strings now.
                # Without 'del', Python keeps them alive until the NEXT loop
                # iteration assigns new values. Explicit del frees them
                # immediately so the allocator can reuse that memory sooner.
                del phrase, translation

                # ── Periodic checkpoint ───────────────────────────────────────
                # Write checkpoint every CHECKPOINT_EVERY rows so a crash
                # between Chrome restarts loses at most CHECKPOINT_EVERY rows.
                if rows_done % CHECKPOINT_EVERY == 0:
                    save_checkpoint(output_folder, input_folder,
                                    file_index, rows_done, num)

                # ── Periodic Python garbage collection ────────────────────────
                # gc.collect() tells Python to look for and free objects that
                # are no longer referenced. Called manually here because the
                # automatic GC may not trigger often enough during a tight loop.
                if rows_done % GC_EVERY == 0:
                    gc.collect()

                # ── Periodic RAM log ──────────────────────────────────────────
                # Prints current memory usage if psutil is installed.
                if LOG_EVERY and rows_done % LOG_EVERY == 0:
                    log_ram(f"phrase {rows_done}/{total}")

                # ── Periodic Chrome restart ───────────────────────────────────
                # This is the most important RAM optimisation.
                # Chrome's renderer process accumulates leaked heap objects
                # over time that cannot be freed short of restarting the
                # process entirely. We do that here on a fixed schedule.
                # A checkpoint is force-saved just before the restart so
                # a crash during the restart loses exactly zero rows.
                if rows_done % CHROME_RESTART_EVERY == 0:
                    log.info(
                        f"  [Chrome restart] {rows_done} phrases done — "
                        f"restarting Chrome to reclaim RAM ..."
                    )
                    save_checkpoint(output_folder, input_folder,
                                    file_index, rows_done, num)
                    driver = restart_driver(driver)
                    # 'driver' now refers to the new Chrome instance.
                    # The loop continues translating with the new driver.

    except KeyboardInterrupt:
        # Ctrl+C pressed outside translate_phrase (e.g. during a sleep).
        log.warning("\n  Ctrl+C detected. Saving checkpoint ...")
        save_checkpoint(output_folder, input_folder, file_index, rows_done, "")
        return False, True, driver

    except Exception as exc:
        log.error(f"  Unexpected error during processing: {exc}", exc_info=True)
        return False, False, driver

    log.info(f"  Done. Wrote {rows_done} row(s) -> {output_path.name}")
    log_ram("end of file")
    return True, False, driver


# ══════════════════════════════════════════════════════════════════════════════
#  BATCH RUNNER
#
#  Orchestrates the full run:
#    1. Prompts for folders
#    2. Checks for a checkpoint and asks about resuming
#    3. Discovers all input files in the input folder
#    4. Starts Chrome
#    5. Calls process_file for each input file
#    6. Handles Ctrl+C between files
#    7. Cleans up the checkpoint on full completion
# ══════════════════════════════════════════════════════════════════════════════

def run_batch() -> None:
    """
    Main entry point for the batch translation run.
    Called automatically when you run:  python auto_translation_batch.py
    """
    input_folder, output_folder = prompt_folders()

    # Create the output folder if it does not already exist.
    # parents=True means intermediate directories are created too.
    output_folder.mkdir(parents=True, exist_ok=True)

    # ── Check for a saved checkpoint ──────────────────────────────────────────
    # If translation_checkpoint.json exists in the output folder, a previous
    # run was interrupted. Ask the user whether to resume or restart.
    checkpoint  = load_checkpoint(output_folder)
    resume_from = 1     # file index to start/resume from (1-based)
    resume_rows = 0     # rows already done in the resume file

    if checkpoint:
        do_resume = prompt_resume(checkpoint)
        if do_resume:
            # Pick up exactly where we left off
            resume_from = checkpoint["file_index"]
            resume_rows = checkpoint["rows_done"]
            log.info(f"  Resuming: file #{resume_from}, row {resume_rows + 1}")
        else:
            # User chose a fresh start — wipe the checkpoint
            delete_checkpoint(output_folder)

    # ── Discover input files ──────────────────────────────────────────────────
    # Sort alphabetically so the processing order is predictable.
    # Only files with a supported extension (.txt, .csv) are included.
    # Subfolders and hidden files are ignored.
    input_files = sorted(
        p for p in input_folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )

    if not input_files:
        log.warning(f"No supported files found in {input_folder.resolve()}")
        log.warning(f"Supported extensions: {', '.join(SUPPORTED_EXTS)}")
        return

    log.info(f"Found {len(input_files)} file(s) to process.")
    log_ram("before driver start")

    driver        = build_driver()
    success_count = 0
    failure_count = 0

    try:
        for idx, input_path in enumerate(input_files, start=1):
            # Each input file maps to one numbered output file
            output_filename = f"{OUTPUT_PREFIX}_{idx}.csv"
            output_path     = output_folder / output_filename

            # ── Skip files fully completed in a previous run ──────────────────
            if idx < resume_from:
                log.info(
                    f"[{idx}/{len(input_files)}]  {input_path.name}"
                    f"  -> already complete, skipping."
                )
                success_count += 1
                continue

            log.info("-" * 60)
            log.info(f"[{idx}/{len(input_files)}]  {input_path.name}"
                     f"  ->  {output_filename}")

            # Determine resume parameters for this specific file.
            # Only the file we are resuming from gets skip/append treatment;
            # all subsequent files start fresh.
            skip   = resume_rows if idx == resume_from else 0
            append = (idx == resume_from and resume_rows > 0)

            try:
                completed, paused, driver = process_file(
                    driver        = driver,
                    input_path    = input_path,
                    output_path   = output_path,
                    output_folder = output_folder,
                    input_folder  = input_folder,
                    file_index    = idx,
                    skip_rows     = skip,
                    append_mode   = append,
                )

                if paused:
                    # User pressed Ctrl+C — checkpoint already saved inside
                    # process_file. Exit cleanly; run again to resume.
                    log.info("  Run paused. Run the script again to resume.")
                    return

                if completed:
                    success_count += 1
                    log.info(f"  OK: {input_path.name}")
                    # Advance checkpoint so the next run skips this file
                    save_checkpoint(output_folder, input_folder,
                                    file_index=idx + 1, rows_done=0)
                else:
                    failure_count += 1
                    log.warning(f"  Skipped/failed: {input_path.name}")

            except KeyboardInterrupt:
                # Ctrl+C pressed in the gap between two files.
                # Save a checkpoint pointing to the start of the current file
                # so the next run begins this file from the top.
                log.warning("\n  Ctrl+C between files. Progress saved.")
                save_checkpoint(output_folder, input_folder,
                                file_index=idx, rows_done=0)
                return

            # After a file completes, clear the resume counters so the NEXT
            # file in the loop is always treated as a fresh start.
            resume_from = idx + 1
            resume_rows = 0

            # Collect Python garbage between files
            gc.collect()
            log_ram(f"after file {idx}")

    finally:
        # This block runs no matter how the loop exits — normal completion,
        # Ctrl+C, or an unhandled exception — so Chrome always gets closed.
        try:
            driver.quit()
        except Exception:
            pass
        log.info("Chrome closed.")
        gc.collect()
        log_ram("final")

    # ── All files finished — clean up checkpoint ──────────────────────────────
    # Deleting the checkpoint prevents the next run from asking about resuming.
    delete_checkpoint(output_folder)

    log.info("=" * 60)
    log.info("BATCH COMPLETE")
    log.info(f"  Total files : {len(input_files)}")
    log.info(f"  Successful  : {success_count}")
    log.info(f"  Failed      : {failure_count}")
    log.info(f"  Output      : {output_folder.resolve()}")
    log.info("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
#  Python runs this block when you execute the script directly.
#  It does NOT run if another script imports this file as a module.
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_batch()
