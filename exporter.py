import sys
import subprocess
import shutil
import os
import argparse
import urllib.request
import zipfile
import platform
import math

def pip_install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    from pydub import AudioSegment
except ImportError:
    pip_install("pydub")
    from pydub import AudioSegment

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

    bin_path = os.path.join(dest_folder, extracted_dir, "bin")
    return bin_path

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

def main():
    check_and_setup_ffmpeg()

    parser = argparse.ArgumentParser(description="🎵 Mix .ogg files with offsets, durations, scales, pitch into one output.ogg")
    parser.add_argument("--files", nargs="+", required=True, help="List of input .ogg files")
    parser.add_argument("--offsets", nargs="+", type=float, required=True, help="Start time (seconds) for each file")
    parser.add_argument("--lengths", nargs="+", type=float, required=True, help="Duration (seconds) for each file")
    parser.add_argument("--volumes", nargs="+", type=float, required=True, help="Volume scale factor (1.0 = 100%)")
    parser.add_argument("--pitches", nargs="+", type=float, required=True, help="Pitch scale factor (e.g. 1.0 = original, 2.0 = +1 octave)")
    parser.add_argument("--output", default="output.ogg", help="Output .ogg filename (default: output.ogg)")
    args = parser.parse_args()

    if not (len(args.files) == len(args.offsets) == len(args.lengths) == len(args.volumes) == len(args.pitches)):
        parser.error("The number of --files, offsets, lengths, volumes and pitches must match.")

    total_end_ms = max(int((off + length) * 1000) for off, length in zip(args.offsets, args.lengths))
    final_mix = AudioSegment.silent(duration=total_end_ms)

    TARGET_FRAME_RATE = 44100

    for file, offset, length, volume, pitch in zip(args.files, args.offsets, args.lengths, args.volumes, args.pitches):
        volume = max(volume, 1e-8)
        pitch = max(pitch, 1e-8)

        audio = AudioSegment.from_ogg(file)
        segment = audio[:int(length * 1000)]

        gain_dB = 20 * math.log10(volume)
        segment = segment + gain_dB

        # Adjust pitch by modifying frame rate
        new_rate = int(segment.frame_rate * pitch)
        pitched = segment._spawn(segment.raw_data, overrides={'frame_rate': new_rate})
        pitched = pitched.set_frame_rate(TARGET_FRAME_RATE)

        final_mix = final_mix.overlay(pitched, position=int(offset * 1000))

    set_status("export", 1)
    final_mix.export(args.output, format="ogg", codec="libvorbis")

if __name__ == "__main__":
    main()