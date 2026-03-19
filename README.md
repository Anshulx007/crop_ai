# Crop AI - Raspberry Pi Hotspot Disease Detection 🌿

A Raspberry Pi based crop disease detection system that creates its own WiFi hotspot and allows a phone to upload crop leaf images through a browser. The Pi processes the image locally using a YOLO classification model, shows the result on LCD + RGB LED, and makes the result available to both phone and laptop.

---

## Features

- Raspberry Pi runs as a **WiFi hotspot**
- Phone connects directly to Pi hotspot
- Upload crop leaf photo from phone browser
- Pi processes image locally using **YOLO classification**
- Cleaned image saved automatically
- Result JSON generated automatically
- **LCD** displays disease + confidence
- **RGB LED** indicates severity
- Phone instantly sees result page
- Laptop on same hotspot can open:
  - `/results` dashboard
  - `/api/results` API
- `watcher.py` downloads cleaned images + JSON for **MATLAB**

---

## System Workflow

1. Raspberry Pi creates hotspot
2. Phone connects to Pi hotspot
3. User opens Flask page on Pi
4. User uploads or captures leaf image
5. Pi saves image in `uploads/`
6. `process_image.py`:
   - cleans image
   - runs YOLO model
   - updates LCD + LED
   - saves cleaned image
   - saves result JSON
7. Phone auto-refreshes until result is ready
8. Laptop watcher downloads results for MATLAB

---

## Project Structure

```bash
crop_ai/
├── app.py
├── process_image.py
├── watcher.py
├── requirements.txt
├── .gitignore
├── README.md
├── uploads/
├── cleaned/
└── results/