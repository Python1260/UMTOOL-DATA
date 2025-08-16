import sys, os, argparse, subprocess, shutil, platform, math, urllib.request, zipfile
import numpy as np

def pip_install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# Ensure lib dependencies
try:
    import librosa
except ImportError:
    pip_install("librosa")
    import librosa

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

def robust_trim(y, sr, enable_trim=True, top_db=60, frame_length=1024, hop_length=256):
    """Optionally trim leading/trailing low-energy regions using librosa.effects.trim."""
    if not enable_trim:
        return y
    # librosa.effects.trim: trims segments top_db dB below max RMS; tweak hop_length for precision.
    yt, _ = librosa.effects.trim(
        y, top_db=top_db, frame_length=frame_length, hop_length=hop_length
    )
    return yt if yt.size > 0 else y

def main():
    check_and_setup_ffmpeg()

    parser = argparse.ArgumentParser(description="Measure normalized RMS volume at spacing intervals (0–1 scale) robustly.")
    parser.add_argument("--input", "-i", required=True, help="Path to .ogg (Vorbis/Opus) or any audio file")
    parser.add_argument("--spacing", "-s", type=float, required=True, help="Interval in seconds between samples")
    parser.add_argument("--no-trim", action="store_true", help="Disable auto-trim of low-energy head/tail")
    parser.add_argument("--trim-db", type=float, default=60.0, help="Top dB below max to consider silence for trimming (default 60)")
    args = parser.parse_args()

    # 1) Load at native rate, mono (librosa uses soundfile when possible; otherwise audioread/ffmpeg).
    # Keep sr=None to avoid resampling (less edge funk). Docs: librosa.load. 
    y, sr = librosa.load(args.input, sr=None, mono=True)

    # 2) (Optional) Trim low-energy leading/trailing chunks to remove codec padding artifacts.
    # This handles typical priming/decoder silence and repeated patterns at edges.
    # See librosa.effects.trim docs.
    y = robust_trim(y, sr, enable_trim=not args.no_trim, top_db=args.trim_db, frame_length=1024, hop_length=256)

    if y.size == 0:
        set_status("")  # empty
        return

    # 3) Compute per-sample power and cumulative sum (double precision for stability).
    power = y.astype(np.float64) ** 2
    cumsum = np.concatenate(([0.0], np.cumsum(power)))

    # 4) Exact, bucketed RMS using cumulative sums (no fencepost errors).
    spacing_samples = max(int(round(args.spacing * sr)), 1)
    n_intervals = int(math.ceil(len(y) / spacing_samples))

    starts = spacing_samples * np.arange(n_intervals, dtype=np.int64)
    ends = np.minimum(starts + spacing_samples, len(y)).astype(np.int64)

    sums = cumsum[ends] - cumsum[starts]
    lengths = (ends - starts).astype(np.float64)
    # Guard against any zero-length (shouldn't happen, but be safe)
    lengths = np.maximum(lengths, 1.0)
    rms = np.sqrt(sums / lengths)

    # Normalize to 0..1
    max_r = float(np.max(rms)) if rms.size else 1.0
    if max_r == 0.0:
        normalized = np.zeros_like(rms, dtype=np.float64)
    else:
        normalized = np.minimum(rms / max_r, 1.0)

    set_status(" ".join(f"{v:.5f}" for v in normalized))

if __name__ == "__main__":
    main()
