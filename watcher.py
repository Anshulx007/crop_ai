#!/usr/bin/env python3

import requests
import json
import os
import time
from pathlib import Path
from datetime import datetime

# ========== CONFIGURATION ==========
PI_URL = "http://192.168.4.1:5000"   # Pi hotspot IP
POLL_INTERVAL = 5                    # seconds

# Where to save for MATLAB (Laptop/Windows)
CLEANED_FOLDER = r"C:\Users\hp\crop_ai\cleaned"
RESULTS_FOLDER = r"C:\Users\hp\crop_ai\results"

for folder in [CLEANED_FOLDER, RESULTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

TRACKER_FILE = os.path.join(RESULTS_FOLDER, "_saved.json")
saved_results = set()   # track already saved filenames


def load_saved():
    """Load list of already saved results."""
    global saved_results
    try:
        if os.path.exists(TRACKER_FILE):
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    saved_results = set(data)
                else:
                    saved_results = set()
            print(f"✓ Loaded tracker: {len(saved_results)} already saved")
        else:
            saved_results = set()
    except Exception as e:
        print(f"⚠ Tracker load failed, starting fresh: {e}")
        saved_results = set()


def save_tracker():
    """Persist saved results tracker."""
    try:
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(saved_results)), f, indent=2)
    except Exception as e:
        print(f"⚠ Tracker save failed: {e}")


def fetch_results():
    """Fetch all result JSON entries from Pi."""
    try:
        r = requests.get(f"{PI_URL}/api/results", timeout=10)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except requests.exceptions.ConnectionError:
        print(f"  ⚠ Cannot reach Pi at {PI_URL} — waiting...")
        return []
    except requests.exceptions.Timeout:
        print("  ⚠ Request timed out while contacting Pi")
        return []
    except Exception as e:
        print(f"  ⚠ Error fetching results: {e}")
        return []


def download_cleaned_image(clean_filename):
    """Download cleaned image from Pi to laptop."""
    if not clean_filename:
        return False

    dest = os.path.join(CLEANED_FOLDER, clean_filename)

    if os.path.exists(dest):
        return True   # already downloaded

    try:
        r = requests.get(f"{PI_URL}/cleaned/{clean_filename}", timeout=15)
        r.raise_for_status()

        with open(dest, "wb") as f:
            f.write(r.content)

        print(f"  🖼 Image saved: {clean_filename}")
        return True

    except Exception as e:
        print(f"  ⚠ Failed to download image {clean_filename}: {e}")
        return False


def save_result_json(result):
    """Save one result JSON locally for MATLAB."""
    filename = result.get("filename", "")
    if not filename:
        return None

    stem = Path(filename).stem
    out_path = os.path.join(RESULTS_FOLDER, f"{stem}_result.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"  📊 JSON saved: {stem}_result.json")
    return out_path


def poll():
    """Poll Pi API and save any new results."""
    results = fetch_results()
    new_count = 0

    for result in results:
        filename = result.get("filename", "")

        if not filename or filename in saved_results:
            continue

        disease = result.get("class", "?").replace("_", " ").title()
        severity = result.get("severity", "?")
        confidence = result.get("confidence", 0)

        print(f"\n📥 New result: {filename}")
        print(f"   Disease  : {disease}")
        print(f"   Severity : {severity}")
        print(f"   Conf     : {confidence:.2%}")

        # Save JSON for MATLAB
        save_result_json(result)

        # Download cleaned image for MATLAB
        clean_fn = result.get("clean_filename", "")
        if clean_fn:
            download_cleaned_image(clean_fn)

        saved_results.add(filename)
        save_tracker()
        new_count += 1

    return new_count


def main():
    print("=" * 55)
    print("  Crop AI — Laptop Watcher")
    print("=" * 55)
    print(f"  Pi server    : {PI_URL}")
    print(f"  Cleaned imgs : {CLEANED_FOLDER}")
    print(f"  Results JSON : {RESULTS_FOLDER}")
    print(f"  Poll every   : {POLL_INTERVAL}s")
    print("=" * 55)
    print("  Connect laptop to Pi hotspot WiFi")
    print("  MATLAB reads from the folders above")
    print("  Press Ctrl+C to stop")
    print()

    load_saved()

    while True:
        try:
            n = poll()
            if n == 0:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for new results...",
                    end="\r",
                    flush=True
                )

        except KeyboardInterrupt:
            print("\n\nStopped.")
            break

        except Exception as e:
            print(f"\n⚠ Unexpected error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()