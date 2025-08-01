import sys
import subprocess
import shutil
import os
import argparse
import urllib.request
import zipfile
import platform
import math

# ------------------------ Auto Install ------------------------

def pip_install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    from pydub import AudioSegment
except ImportError:
    pip_install("pydub")
    from pydub import AudioSegment

# ------------------------ FFmpeg Setup ------------------------

def set_status(status):
    print(status, flush=True)

def download_and_extract_ffmpeg(dest_folder):
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    os.makedirs(dest_folder, exist_ok=True)
    zip_path = os.path.join(dest_folder, "ffmpeg.zip")

    if not os.path.isfile(zip_path):
        urllib.request.urlretrieve(ffmpeg_url, zip_path)

    extracted_dir = next((d for d in os.listdir(dest_folder) if d.startswith("ffmpeg-")), None)
    if not extracted_dir:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(dest_folder)
        extracted_dir = next((d for d in os.listdir(dest_folder) if d.startswith("ffmpeg-")), None)

    if not extracted_dir:
        sys.exit(1)

    return os.path.join(dest_folder, extracted_dir, "bin")

def check_and_setup_ffmpeg():
    if shutil.which("ffmpeg"):
        return
    if platform.system().lower() != "windows":
        sys.exit(1)
    ffmpeg_local_dir = os.path.join(os.path.dirname(__file__), "ffmpeg")
    ffmpeg_bin = download_and_extract_ffmpeg(ffmpeg_local_dir)
    os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")
    if not shutil.which("ffmpeg"):
        sys.exit(1)

# ------------------------ Main Logic ------------------------

def main():
    check_and_setup_ffmpeg()

    parser = argparse.ArgumentParser(description="Sample normalized intensity using Pydub")
    parser.add_argument("--input", type=str, required=True, help="Input .ogg file path")
    parser.add_argument("--spacing", type=float, required=True, help="Spacing in seconds between samples")
    args = parser.parse_args()

    audio = AudioSegment.from_file(args.input, format="ogg")
    duration_ms = len(audio)  # duration in milliseconds
    spacing_ms = int(args.spacing * 1000)
    intervals = math.ceil(duration_ms / spacing_ms)

    values = []
    for i in range(intervals + 1):
        start_ms = min(i * spacing_ms, duration_ms)
        slice_ms = audio[start_ms:start_ms + spacing_ms]
        rms = slice_ms.rms  # root mean square amplitude
        # convert RMS (0…max) into 0…1
        max_possible = slice_ms.max_possible_amplitude or 1
        val = rms / max_possible
        values.append(val)

    set_status(" ".join(f"{v:.5f}" for v in values))
    

if __name__ == "__main__":
    main()