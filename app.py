from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
from datetime import datetime
import os
import json
import subprocess
import sys
import logging
import threading

app = Flask(__name__)

# ========== CONFIGURATION ==========
BASE_DIR = str(Path(__file__).parent.resolve())
UPLOAD_FOLDER = f"{BASE_DIR}/uploads"
CLEANED_FOLDER = f"{BASE_DIR}/cleaned"
RESULTS_FOLDER = f"{BASE_DIR}/results"
PROCESS_SCRIPT = f"{BASE_DIR}/process_image.py"

for folder in [UPLOAD_FOLDER, CLEANED_FOLDER, RESULTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

logging.basicConfig(
    filename=f"{BASE_DIR}/server.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)


# ========== HOME PAGE — PHONE UPLOAD ==========
@app.route("/")
def index():
    return """<!DOCTYPE html>
<html>
<head>
    <title>Crop AI</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial; background: linear-gradient(135deg, #1b5e20, #2e7d32);
               min-height: 100vh; display: flex; align-items: center;
               justify-content: center; padding: 20px; }
        .card { background: white; border-radius: 20px; padding: 30px;
                max-width: 420px; width: 100%;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        .logo { text-align: center; font-size: 52px; margin-bottom: 8px; }
        h1 { text-align: center; color: #1b5e20; font-size: 24px; margin-bottom: 4px; }
        .sub { text-align: center; color: #999; font-size: 13px; margin-bottom: 25px; }
        .upload-area { border: 3px dashed #81c784; border-radius: 16px;
                       padding: 35px 20px; text-align: center;
                       background: #f1f8e9; cursor: pointer;
                       transition: all 0.3s; margin-bottom: 15px; }
        .upload-area:hover { background: #e8f5e9; border-color: #2e7d32; }
        .upload-icon { font-size: 44px; margin-bottom: 8px; }
        .upload-text { color: #2e7d32; font-weight: bold; font-size: 15px; }
        .upload-hint { color: #999; font-size: 12px; margin-top: 4px; }
        #preview { max-width: 100%; border-radius: 12px; margin-top: 12px;
                   display: none; border: 2px solid #81c784; }
        input[type=file] { display: none; }
        .btn { background: linear-gradient(135deg, #2e7d32, #1b5e20);
               color: white; padding: 15px; border: none; border-radius: 12px;
               font-size: 16px; font-weight: bold; cursor: pointer; width: 100%;
               box-shadow: 0 4px 15px rgba(46,125,50,0.4); }
        .btn:disabled { background: #ccc; cursor: not-allowed; box-shadow: none; }
        #status { margin-top: 14px; padding: 12px; border-radius: 10px;
                  text-align: center; font-size: 14px; font-weight: bold; display: none; }
        .loading { background: #fff8e1; color: #f57f17; }
        .error   { background: #ffebee; color: #c62828; }
        .hist-btn { display: block; text-align: center; margin-top: 15px;
                    color: #2e7d32; font-size: 13px; text-decoration: none; }
    </style>
</head>
<body>
<div class="card">
    <div class="logo">🌿</div>
    <h1>Crop AI</h1>
    <p class="sub">Disease Detection — Pi Hotspot</p>

    <div class="upload-area" onclick="document.getElementById('fileInput').click()">
        <div class="upload-icon">📷</div>
        <div class="upload-text">Take Photo or Upload</div>
        <div class="upload-hint">Tap to capture crop leaf image</div>
        <img id="preview" />
    </div>

    <input type="file" id="fileInput" accept="image/*" capture="environment"
           onchange="previewImage(event)">

    <button class="btn" id="uploadBtn" onclick="uploadFile()" disabled>
        🔬 Analyse Crop
    </button>
    <div id="status"></div>
    <a href="/results" class="hist-btn">📋 View all results</a>
</div>
<script>
function previewImage(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
        const p = document.getElementById('preview');
        p.src = ev.target.result;
        p.style.display = 'block';
        document.getElementById('uploadBtn').disabled = false;
    };
    reader.readAsDataURL(file);
}
async function uploadFile() {
    const file = document.getElementById('fileInput').files[0];
    if (!file) return;
    const btn = document.getElementById('uploadBtn');
    const status = document.getElementById('status');
    btn.disabled = true;
    status.className = 'loading';
    status.style.display = 'block';
    status.innerText = '⏳ Uploading...';
    const fd = new FormData();
    fd.append('file', file);
    try {
        const res = await fetch('/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.success) {
            status.innerText = '🔬 Analysing... please wait';
            window.location.href = '/result/' + data.filename;
        } else {
            status.className = 'error';
            status.innerText = '❌ ' + data.error;
            btn.disabled = false;
        }
    } catch(e) {
        status.className = 'error';
        status.innerText = '❌ ' + e.message;
        btn.disabled = false;
    }
}
</script>
</body>
</html>"""


# ========== UPLOAD — triggers processing ==========
@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(file.filename).suffix.lower() or ".jpg"
    filename = f"crop_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    print(f"📥 Upload: {filename}")
    logging.info(f"Upload: {filename}")

    # Run processing in background so upload response returns immediately
    threading.Thread(
        target=lambda: subprocess.run(
            [sys.executable, PROCESS_SCRIPT, filepath, filename],
            timeout=120
        ),
        daemon=True
    ).start()

    return jsonify({"success": True, "filename": filename}), 200


# ========== RESULT PAGE — phone sees this after upload ==========
@app.route("/result/<filename>")
def result_page(filename):
    stem = Path(filename).stem
    result_path = os.path.join(RESULTS_FOLDER, f"{stem}_result.json")

    # Auto-refresh until result is ready
    if not os.path.exists(result_path):
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="2;url=/result/{filename}">
    <style>
        body {{ font-family: Arial; background: #f1f8e9; display: flex;
               align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
        .card {{ background: white; border-radius: 20px; padding: 40px 30px;
                 text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 360px; }}
        .spinner {{ border: 4px solid #e0e0e0; border-top: 4px solid #2e7d32;
                    border-radius: 50%; width: 52px; height: 52px;
                    animation: spin 1s linear infinite; margin: 20px auto; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        h2 {{ color: #2e7d32; margin-bottom: 5px; }}
        p {{ color: #999; font-size: 13px; }}
    </style>
</head>
<body>
<div class="card">
    <h2>🔬 Analysing...</h2>
    <div class="spinner"></div>
    <p>Pi is processing your image</p>
    <p>Page refreshes automatically</p>
</div>
</body>
</html>""", 200

    with open(result_path, "r", encoding="utf-8") as f:
        r = json.load(f)

    return render_result_html(r)


# ========== ALL RESULTS PAGE — laptop dashboard ==========
@app.route("/results")
def results_page():
    files = sorted(
        [f for f in os.listdir(RESULTS_FOLDER) if f.endswith("_result.json")],
        reverse=True
    )

    rows = ""
    for fname in files[:50]:
        try:
            with open(os.path.join(RESULTS_FOLDER, fname), "r", encoding="utf-8") as f:
                r = json.load(f)

            disease = r["class"].replace("_", " ").title()
            conf = r["confidence"] * 100
            sev = r.get("severity", "?")
            ts = r.get("timestamp", "")[:19].replace("T", " ")

            colors = {
                "None": "#2e7d32",
                "Low": "#388e3c",
                "Medium": "#f57c00",
                "High": "#c62828"
            }
            col = colors.get(sev, "#555")

            rows += f"""
            <tr onclick="window.location='/result/{r['filename']}'" style="cursor:pointer">
                <td>{ts}</td>
                <td><b>{disease}</b></td>
                <td style="color:{col};font-weight:bold">{sev}</td>
                <td>{conf:.1f}%</td>
            </tr>"""
        except Exception:
            pass

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Crop AI Results</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="10">
    <style>
        body {{ font-family: Arial; background: #f1f8e9; padding: 20px; margin: 0; }}
        h1 {{ color: #1b5e20; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; background: white;
                 border-radius: 12px; overflow: hidden;
                 box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
        th {{ background: #2e7d32; color: white; padding: 12px 15px;
              text-align: left; font-size: 13px; }}
        td {{ padding: 12px 15px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }}
        tr:hover {{ background: #f1f8e9; }}
        .back {{ display: inline-block; margin-bottom: 15px; color: #2e7d32;
                 text-decoration: none; font-weight: bold; }}
        .refresh {{ color: #999; font-size: 12px; margin-bottom: 10px; }}
    </style>
</head>
<body>
    <a href="/" class="back">← New Photo</a>
    <h1>🌿 All Results</h1>
    <p class="refresh">Auto-refreshes every 10s</p>
    <table>
        <tr><th>Timestamp</th><th>Disease</th><th>Severity</th><th>Confidence</th></tr>
        {rows if rows else '<tr><td colspan="4" style="text-align:center;color:#999;padding:30px">No results yet</td></tr>'}
    </table>
</body>
</html>"""


# ========== API — laptop watcher polls this ==========
@app.route("/api/results")
def api_results():
    results = []

    for fname in os.listdir(RESULTS_FOLDER):
        if fname.endswith("_result.json"):
            try:
                with open(os.path.join(RESULTS_FOLDER, fname), "r", encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception:
                pass

    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(results), 200


# ========== SERVE CLEANED IMAGES ==========
@app.route("/cleaned/<filename>")
def serve_cleaned(filename):
    return send_from_directory(CLEANED_FOLDER, filename)


# ========== HELPER: render result HTML ==========
def render_result_html(r):
    disease = r["class"].replace("_", " ").title()
    conf = r["confidence"] * 100
    severity = r.get("severity", "Unknown")
    treat = r["treatment"]
    ts = r.get("timestamp", "")[:19].replace("T", " ")

    col_map = {
        "healthy": "#2e7d32",
        "early blight": "#e65100",
        "bacterial spot": "#c62828",
        "late blight": "#6a1b9a"
    }
    col = col_map.get(disease.lower(), "#424242")

    sev_col = {
        "none": "#2e7d32",
        "low": "#388e3c",
        "medium": "#f57c00",
        "high": "#c62828"
    }.get(severity.lower(), "#555")

    prob_bars = ""
    if "all_probs" in r:
        for cls, prob in sorted(r["all_probs"].items(), key=lambda x: -x[1]):
            label = cls.replace("_", " ").title()
            pct = prob * 100
            prob_bars += f"""
            <div style="margin-bottom:8px">
                <div style="display:flex;justify-content:space-between;
                            font-size:12px;color:#555;margin-bottom:3px">
                    <span>{label}</span><span>{pct:.1f}%</span>
                </div>
                <div style="background:#e0e0e0;border-radius:6px;height:8px">
                    <div style="width:{pct:.1f}%;background:{col};
                                border-radius:6px;height:8px;
                                min-width:2px"></div>
                </div>
            </div>"""

    clean_img = r.get("clean_filename", "")

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Result — {disease}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing:border-box; margin:0; padding:0; }}
        body {{ font-family:Arial; background:#f1f8e9; min-height:100vh;
               display:flex; align-items:center; justify-content:center; padding:20px; }}
        .box {{ background:white; border-radius:20px; overflow:hidden;
                box-shadow:0 10px 40px rgba(0,0,0,0.15); max-width:460px; width:100%; }}
        .hdr {{ background:{col}; color:white; padding:30px 20px; text-align:center; }}
        .disease {{ font-size:28px; font-weight:bold; text-transform:uppercase; }}
        .badge {{ display:inline-block; background:{sev_col}; padding:5px 14px;
                  border-radius:20px; font-size:11px; font-weight:bold; margin-top:8px; }}
        .body {{ padding:20px; }}
        img {{ width:100%; border-radius:10px; margin-bottom:15px;
               border:2px solid #e0e0e0; }}
        .box1 {{ background:#f5f5f5; padding:15px; border-radius:12px;
                 border-left:4px solid {col}; margin-bottom:12px; }}
        .lbl {{ font-size:10px; color:#888; text-transform:uppercase;
                font-weight:bold; margin-bottom:4px; }}
        .val {{ font-size:26px; font-weight:bold; color:{col}; }}
        .tbox {{ background:#f1f8e9; padding:15px; border-radius:12px;
                 border-left:4px solid #2e7d32; margin-bottom:12px; }}
        .tlbl {{ font-size:10px; color:#2e7d32; text-transform:uppercase;
                 font-weight:bold; margin-bottom:6px; }}
        .ttxt {{ font-size:13px; color:#333; line-height:1.6; }}
        .probs {{ background:#fafafa; padding:15px; border-radius:12px; margin-bottom:12px; }}
        .ts {{ text-align:center; font-size:11px; color:#bbb; margin-bottom:12px; }}
        .btns {{ display:flex; gap:10px; }}
        .btn {{ flex:1; padding:13px; border:none; border-radius:10px;
                font-size:14px; font-weight:bold; cursor:pointer; }}
        .p {{ background:{col}; color:white; }}
        .s {{ background:#e0e0e0; color:#333; }}
    </style>
</head>
<body>
<div class="box">
    <div class="hdr">
        <div class="disease">🌿 {disease}</div>
        <div class="badge">● {severity.upper()} SEVERITY</div>
    </div>
    <div class="body">
        {'<img src="/cleaned/' + clean_img + '" onerror="this.style.display=\\'none\\'">' if clean_img else ''}
        <div class="ts">{ts}</div>
        <div class="box1">
            <div class="lbl">Confidence Score</div>
            <div class="val">{conf:.1f}%</div>
        </div>
        <div class="tbox">
            <div class="tlbl">✓ Treatment Recommendation</div>
            <div class="ttxt">{treat}</div>
        </div>
        <div class="probs">
            <div class="lbl" style="margin-bottom:10px">All Classes</div>
            {prob_bars}
        </div>
        <div class="btns">
            <button class="btn p" onclick="location.href='/'">📷 New Photo</button>
            <button class="btn s" onclick="location.href='/results'">📋 All Results</button>
        </div>
    </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    print("=" * 50)
    print("🌿 Crop AI — Pi Hotspot Server")
    print("=" * 50)
    print("  Local      → http://127.0.0.1:5000/")
    print("  Results    → http://127.0.0.1:5000/results")
    print("  API        → http://127.0.0.1:5000/api/results")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)