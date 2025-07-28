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

def set_status(name, rel):
    print(f"{name}${rel}", flush=True)

def download_progress(count, block_size, total_size):
    downloaded = count * block_size
    percent = int(min(1, downloaded / total_size))
    set_status("download", percent)

def download_and_extract_ffmpeg(dest_folder):
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    os.makedirs(dest_folder, exist_ok=True)
    zip_path = os.path.join(dest_folder, "ffmpeg.zip")

    if not os.path.isfile(zip_path):
        urllib.request.urlretrieve(ffmpeg_url, zip_path, reporthook=download_progress)

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

    parser = argparse.ArgumentParser(description="🎵 Mix .ogg files with offsets, durations, volumes, and pitch scales.")
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--offsets", nargs="+", type=float, required=True)
    parser.add_argument("--lengths", nargs="+", type=float, required=True)
    parser.add_argument("--volumes", nargs="+", type=float, required=True)
    parser.add_argument("--pitches", nargs="+", type=float, required=True,
                        help="Pitch scale (e.g. 1.0 = original, 0.5 = slower & lower)")
    parser.add_argument("--output", default="output.ogg")
    args = parser.parse_args()

    if not (len(args.files) == len(args.offsets) == len(args.lengths) == len(args.volumes) == len(args.pitches)):
        parser.error("All lists (--files, --offsets, --lengths, --volumes, --pitches) must be the same length.")

    # Estimate final duration (since slower pitch increases it)
    est_end_times = []
    for off, length, pitch in zip(args.offsets, args.lengths, args.pitches):
        pitch = max(pitch, 1e-8)
        est_end_times.append(off + length / pitch)
    total_end_ms = int(max(est_end_times) * 1000)

    final_mix = AudioSegment.silent(duration=total_end_ms)

    for file, offset, length, volume, pitch in zip(args.files, args.offsets, args.lengths, args.volumes, args.pitches):
        volume = max(volume, 1e-8)
        pitch = max(pitch, 1e-8)

        audio = AudioSegment.from_ogg(file)
        segment = audio[:int(length * 1000)]

        # Apply pitch shift by changing frame_rate (and DO NOT resample)
        new_frame_rate = int(segment.frame_rate * pitch)
        segment = segment._spawn(segment.raw_data, overrides={"frame_rate": new_frame_rate})

        # Volume adjustment (in dB)
        gain_db = 20 * math.log10(volume)
        segment = segment + gain_db

        final_mix = final_mix.overlay(segment, position=int(offset * 1000))

    set_status("export", 1)
    final_mix.export(args.output, format="ogg", codec="libvorbis")

if __name__ == "__main__":
    main()
