import sys
import os
import argparse
import subprocess
import shutil
import platform
import math
import urllib.request
import zipfile

def pip_install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# Ensure lib dependencies
try:
    import librosa
except ImportError:
    pip_install("librosa")
    import librosa

try:
    import numba
except ImportError:
    pip_install("numba")
    import numba

# Optional - if ffmpeg not installed (common on Windows), bundle download
def download_and_extract_ffmpeg(dest):
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    os.makedirs(dest, exist_ok=True)
    zipf = os.path.join(dest, "ffmpeg.zip")
    if not os.path.exists(zipf):
        urllib.request.urlretrieve(url, zipf)
    with zipfile.ZipFile(zipf, "r") as z:
        z.extractall(dest)
    sub = next(d for d in os.listdir(dest) if d.startswith("ffmpeg-"))
    return os.path.join(dest, sub, "bin")

def check_and_setup_ffmpeg():
    if shutil.which("ffmpeg"):
        return
    if platform.system().lower() != "windows":
        return
    bindir = download_and_extract_ffmpeg(os.path.join(os.path.dirname(__file__), "ffmpeg"))
    os.environ["PATH"] = bindir + os.pathsep + os.environ.get("PATH", "")

def set_status(line):
    print(line, flush=True)

def main():
    check_and_setup_ffmpeg()

    parser = argparse.ArgumentParser(description="Measure normalized RMS volume at spacing intervals (0‑1 scale).")
    parser.add_argument("--input", "-i", required=True, help="Path to .ogg (or any) audio file")
    parser.add_argument("--spacing", "-s", type=float, required=True, help="Interval in seconds between samples")
    args = parser.parse_args()

    # Load file; returns float samples between –1.0 and +1.0
    y, sr = librosa.load(args.input, sr=None, mono=False)

    # If stereo, average the channels into mono
    if y.ndim > 1:
        y = y.mean(axis=0)

    total_samples = len(y)
    spacing_samples = max(int(args.spacing * sr), 1)
    intervals = math.ceil(total_samples / spacing_samples)

    # Compute RMS per interval
    rms_values = []
    for i in numba.prange(intervals + 1):
        start = min(i * spacing_samples, total_samples)
        segment = y[start : min(start + spacing_samples, total_samples)]
        if segment.size == 0:
            rms = 0.0
        else:
            rms = float((segment**2).mean())**0.5  # sqrt(mean(x^2))
        rms_values.append(rms)

    # Optionally normalize with the max RMS (so top segment = 1.0)
    max_rms = max(rms_values) or 1.0
    normalized = [min(r / max_rms, 1.0) for r in rms_values]

    set_status(" ".join(f"{v:.5f}" for v in normalized))

if __name__ == "__main__":
    main()