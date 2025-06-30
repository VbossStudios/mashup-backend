import subprocess
import os

def separate_stems(audio_path, output_dir, label):
    target_dir = os.path.join(output_dir, f"stems_{label}")
    os.makedirs(target_dir, exist_ok=True)
    
    command = [
        "python", "-m", "demucs.separate",
        "--two-stems", "vocals",
        "--out", target_dir,
        audio_path
    ]
    
    subprocess.run(command, check=True)

    song_name = os.path.splitext(os.path.basename(audio_path))[0]
    vocals = os.path.join(target_dir, "htdemucs", song_name, "vocals.wav")
    instr = os.path.join(target_dir, "htdemucs", song_name, "no_vocals.wav")
    return vocals, instr
