#!/usr/bin/env python3
"""
process_image.py — called by app.py for each uploaded image
Usage: python3 process_image.py <filepath> <filename>

Cleans image, runs YOLO classification, updates LCD + LED,
saves cleaned image + result JSON.
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path

# Optional imports (so repo can still open in Codespaces without Pi hardware libs)
try:
    import cv2
except ImportError:
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

try:
    from RPLCD.i2c import CharLCD
except ImportError:
    CharLCD = None

try:
    import lgpio
except ImportError:
    lgpio = None

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    hf_hub_download = None


# ========== CONFIGURATION ==========
BASE_DIR = str(Path(__file__).parent.resolve())
CLEANED_FOLDER = f"{BASE_DIR}/cleaned"
RESULTS_FOLDER = f"{BASE_DIR}/results"
MODEL_PATH = f"{BASE_DIR}/best_yolox_v2.pt"   # changed from best.pt to HF-downloaded model

LCD_ROWS = 2
LCD_COLS = 16
I2C_ADDR = 0x27

LED_RED = 17
LED_GREEN = 27
LED_BLUE = 22

for folder in [CLEANED_FOLDER, RESULTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

logging.basicConfig(
    filename=f"{BASE_DIR}/process.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ========== DISEASE DATABASE ==========
DISEASE_INFO = {
    "healthy": {
        "severity": "None",
        "treatment": "No treatment needed. Continue regular monitoring."
    },
    "early_blight": {
        "severity": "Low",
        "treatment": "Apply fungicide (chlorothalonil). Rotate crops. Remove infected debris."
    },
    "bacterial_spot": {
        "severity": "Medium",
        "treatment": "Apply copper-based bactericide. Remove infected leaves. Avoid overhead watering."
    },
    "late_blight": {
        "severity": "High",
        "treatment": "Apply systemic fungicide immediately. Destroy infected plants. Improve air circulation."
    },
}


def get_disease_info(cls_name: str):
    return DISEASE_INFO.get(
        cls_name,
        {"severity": "Unknown", "treatment": "Monitor plant closely and consult an agronomist."}
    )


# ========== MODEL LOAD (GLOBAL / ONCE) ==========
MODEL = None

def load_model():
    global MODEL

    if YOLO is None:
        raise RuntimeError("ultralytics not installed")

    if not os.path.exists(MODEL_PATH):
        if hf_hub_download is None:
            raise RuntimeError("huggingface_hub not installed")

        hf_hub_download(
            repo_id="Anshulx007/tomato",
            filename="best_yolox_v2.pt",
            repo_type="model",
            local_dir=BASE_DIR
        )

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    if MODEL is None:
        MODEL = YOLO(MODEL_PATH)
        logging.info(f"Model loaded: {MODEL_PATH}")

    return MODEL


# ========== IMAGE PROCESSING ==========
def clean_image(path):
    if cv2 is None:
        raise RuntimeError("opencv-python not installed")

    img = cv2.imread(path)
    if img is None:
        return None

    img = cv2.resize(img, (320, 320))

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(l)
    img = cv2.merge([l, a, b])
    img = cv2.cvtColor(img, cv2.COLOR_LAB2BGR)

    img = cv2.bilateralFilter(img, 9, 75, 75)
    return img


def run_model(model, path):
    results = model.predict(path, verbose=False)
    result = results[0]

    # Safety check: this script expects a CLASSIFICATION model
    if not hasattr(result, "probs") or result.probs is None:
        raise RuntimeError("Model output has no classification probabilities. Use a YOLO classification model.")

    class_idx = int(result.probs.top1)
    class_name = result.names[class_idx]
    confidence = float(result.probs.top1conf.cpu().numpy())

    probs_arr = result.probs.data.cpu().numpy()
    all_probs = {
        result.names[i]: round(float(probs_arr[i]), 6)
        for i in range(len(probs_arr))
    }

    return {
        "class": class_name,
        "confidence": confidence,
        "all_probs": all_probs
    }


# ========== MAIN ==========
def main():
    if len(sys.argv) < 3:
        print("Usage: python3 process_image.py <filepath> <filename>")
        sys.exit(1)

    filepath = sys.argv[1]
    filename = sys.argv[2]
    stem = Path(filename).stem

    lcd = LCD()
    led = LED()

    try:
        # Load model
        lcd.show("Loading model", "Please wait")
        model = load_model()
        print("✓ Model loaded")

        # Clean image
        lcd.show("Cleaning...", filename[:16])
        led.blue()

        clean_img = clean_image(filepath)
        if clean_img is None:
            raise RuntimeError("Could not read uploaded image")

        clean_filename = f"{stem}_clean.jpg"
        clean_path = os.path.join(CLEANED_FOLDER, clean_filename)

        ok = cv2.imwrite(clean_path, clean_img)
        if not ok:
            raise RuntimeError("Failed to save cleaned image")

        print(f"✓ Cleaned: {clean_filename}")

        # Run model
        lcd.show("Analysing...", "Please wait")
        result = run_model(model, clean_path)
        info = get_disease_info(result["class"])

        # Build result JSON
        result_data = {
            "filename": filename,
            "clean_filename": clean_filename,
            "timestamp": datetime.now().isoformat(),
            "class": result["class"],
            "confidence": result["confidence"],
            "severity": info["severity"],
            "treatment": info["treatment"],
            "all_probs": result["all_probs"],
        }

        # Save result JSON
        result_path = os.path.join(RESULTS_FOLDER, f"{stem}_result.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2)

        print(f"✓ Result saved: {result_path}")
        logging.info(
            f"Done: {filename} -> {result['class']} "
            f"[{info['severity']}] {result['confidence']:.2%}"
        )

        # Update LCD + LED
        disease = result["class"].replace("_", " ").title()[:16]
        line2 = f"{result['confidence']:.0%} {info['severity']}"[:16]
        lcd.show(disease, line2)
        led.set_severity(info["severity"])

        print(f"✓ {result['class']} | {info['severity']} | {result['confidence']:.2%}")

    except Exception as e:
        print(f"✗ Error: {e}")
        logging.exception(f"process_image error for {filename}: {e}")
        lcd.show("Error", str(e)[:16])
        led.red()
        sys.exit(1)

    finally:
        # Keep LED showing result color; do not cleanup here
        pass


if __name__ == "__main__":
    main()
