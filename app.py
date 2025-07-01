# app.py
# FastAPI backend for Mixy-style audio mashup

import os
import uuid
import subprocess
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import librosa
import soundfile as sf

app = FastAPI()

# Directories for uploads and outputs
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
for d in (UPLOAD_DIR, OUTPUT_DIR):
    os.makedirs(d, exist_ok=True)

# Utility to download audio from a video URL using yt-dlp
async def download_audio_from_url(url: str, output_path: str):
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "-o", output_path,
        url
    ]
    subprocess.run(cmd, check=True)

# Utility to separate stems using Demucs (vocal + instrumental)
def separate_stems(input_path: str, out_dir: str):
    # demucs will create a subfolder under out_dir
    cmd = ["demucs", "-d", "cpu", "-o", out_dir, input_path]
    subprocess.run(cmd, check=True)
    # Flatten stems from demucs output
    stems_folder = os.path.join(out_dir, os.listdir(out_dir)[0])
    return stems_folder

# Utility to detect BPM (tempo) using librosa
def detect_bpm(audio_path: str) -> float:
    y, sr = librosa.load(audio_path, sr=None)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(tempo)

# Utility to adjust speed (tempo) and pitch using ffmpeg
# pitch in semitones, speed multiplier
async def adjust_speed_and_pitch(
    input_path: str, output_path: str, speed: float = 1.0, pitch_semitones: float = 0.0
):
    # Build ffmpeg filter chain: asetrate for speed, rubberband for pitch
    # Requires ffmpeg compiled with rubberband
    filter_chain = []
    if speed != 1.0:
        filter_chain.append(f"atempo={speed}")
    if pitch_semitones != 0.0:
        filter_chain.append(f"rubberband=pitch={pitch_semitones}")
    filter_str = ",".join(filter_chain)
    cmd = ["ffmpeg", "-y", "-i", input_path]
    if filter_chain:
        cmd += ["-af", filter_str]
    cmd += [output_path]
    subprocess.run(cmd, check=True)

@app.post("/mashup")
async def mashup(
    file1: UploadFile = File(None),
    file2: UploadFile = File(None),
    url1: str = Form(None),
    url2: str = Form(None),
    speed: float = Form(1.0),
    pitch: float = Form(0.0),
    mix_volume: float = Form(0.5),
    section1_start: float = Form(0.0),
    section1_duration: float = Form(None),
    section2_start: float = Form(0.0),
    section2_duration: float = Form(None),
):
    """
    Endpoint to upload two audio inputs (files or URLs), separate stems,
    adjust pitch/speed, mix vocals of one with instrumental of the other,
    and return a downloadable MP3.
    """
    job_id = str(uuid.uuid4())
    base_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(base_dir, exist_ok=True)

    # Save or download input files
    paths = []
    for idx, (f, url) in enumerate(((file1, url1), (file2, url2)), start=1):
        if url:
            out_path = os.path.join(base_dir, f"input{idx}.wav")
            await download_audio_from_url(url, out_path)
        elif f:
            ext = os.path.splitext(f.filename)[1]
            out_path = os.path.join(base_dir, f"input{idx}{ext}")
            with open(out_path, "wb") as buf:
                buf.write(await f.read())
        else:
            raise HTTPException(status_code=400, detail=f"Provide file{idx} or url{idx}")
        paths.append(out_path)

    # Separate stems
    stems1 = separate_stems(paths[0], os.path.join(base_dir, "stems1"))
    stems2 = separate_stems(paths[1], os.path.join(base_dir, "stems2"))

    # Paths to vocal and instrumental stems
    vocal1 = os.path.join(stems1, "vocals.wav")
    inst1 = os.path.join(stems1, "no_vocals.wav")
    vocal2 = os.path.join(stems2, "vocals.wav")
    inst2 = os.path.join(stems2, "no_vocals.wav")

    # Crop selected sections
    def crop(input_path, start, dur, out_path):
        cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", str(start)]
        if dur:
            cmd += ["-t", str(dur)]
        cmd += [out_path]
        subprocess.run(cmd, check=True)

    crop(os.path.join(stems1, "vocals.wav"), section1_start, section1_duration, os.path.join(base_dir, "voc1_cut.wav"))
    crop(os.path.join(stems2, "no_vocals.wav"), section2_start, section2_duration, os.path.join(base_dir, "inst2_cut.wav"))

    # Adjust speed & pitch on both cropped stems
    await adjust_speed_and_pitch(os.path.join(base_dir, "voc1_cut.wav"), os.path.join(base_dir, "voc1_final.wav"), speed, pitch)
    await adjust_speed_and_pitch(os.path.join(base_dir, "inst2_cut.wav"), os.path.join(base_dir, "inst2_final.wav"), speed, pitch)

    # Mix adjusted stems together
    final_path = os.path.join(base_dir, f"{job_id}.mp3")
    cmd_mix = [
        "ffmpeg", "-y",
        "-i", os.path.join(base_dir, "voc1_final.wav"),
        "-i", os.path.join(base_dir, "inst2_final.wav"),
        "-filter_complex",
        f"[0:a]volume={mix_volume}[a];[1:a]volume={1-mix_volume}[b];[a][b]amix=inputs=2:duration=first",
        "-c:a", "libmp3lame",
        final_path
    ]
    subprocess.run(cmd_mix, check=True)

    return {"download_url": f"/download/{job_id}/{job_id}.mp3"}

@app.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    file_path = os.path.join(OUTPUT_DIR, job_id, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="audio/mpeg", filename=filename)
```
