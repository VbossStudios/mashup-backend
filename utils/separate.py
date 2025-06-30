import subprocess
import os

def separate_stems(audio_path, output_dir, label):
    target_dir = os.path.join(output_dir, f"stems_{label}")
    os.makedirs(target_dir, exist_ok=True)

    command = [
        "demucs",
        "--two-stems", "vocals",
        "-n", "htdemucs",  # Explicitly define model
        "--out", target_dir,
        audio_path
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    
    # Log if something goes wrong
    if result.returncode != 0:
        print("Demucs failed:", result.stderr)
        raise RuntimeError("Demucs separation failed.")

    song_name = os.path.splitext(os.path.basename(audio_path))[0]
    vocals = os.path.join(target_dir, "htdemucs", song_name, "vocals.wav")
    instr = os.path.join(target_dir, "htdemucs", song_name, "no_vocals.wav")

    return vocals, instr
