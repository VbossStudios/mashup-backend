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

# Utility to separate stems using Demucs (v4)
def separate_stems(input_path: str, out_dir: str) -> str:
    cmd = ["demucs", "-d", "cpu", "-o", out_dir, input_path]
    subprocess.run(cmd, check=True)
    # Demucs creates a subfolder under out_dir
    folder = os.listdir(out_dir)[0]
    return os.path.join(out_dir, folder)

# Utility to detect BPM (tempo)
def detect_bpm(audio_path: str) -> float:
    y, sr = librosa.load(audio_path, sr=None)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(tempo)

# Utility to adjust speed and pitch using ffmpeg and rubberband
def adjust_speed_and_pitch(input_path: str, output_path: str, speed: float = 1.0, pitch_semitones: float = 0.0):
    filters = []
    if speed != 1.0:
        filters.append(f"atempo={speed}")
    if pitch_semitones != 0.0:
        filters.append(f"rubberband=pitch={pitch_semitones}")
    cmd = ["ffmpeg", "-y", "-i", input_path]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd.append(output_path)
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
    """Combine two inputs, separate stems, adjust settings, and return an MP3 mashup"""
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    inputs = []
    for idx, (f, url) in enumerate(((file1, url1), (file2, url2)), start=1):
        if url:
            path = os.path.join(job_dir, f"input{idx}.wav")
            await download_audio_from_url(url, path)
        elif f:
            ext = os.path.splitext(f.filename)[1]
            path = os.path.join(job_dir, f"input{idx}{ext}")
            with open(path, "wb") as buf:
                buf.write(await f.read())
        else:
            raise HTTPException(status_code=400, detail=f"Provide file{idx} or url{idx}")
        inputs.append(path)

    stems1 = separate_stems(inputs[0], os.path.join(job_dir, "stems1"))
    stems2 = separate_stems(inputs[1], os.path.join(job_dir, "stems2"))

    vocal1 = os.path.join(stems1, "vocals.wav")
    inst2 = os.path.join(stems2, "no_vocals.wav")

    # Crop sections
def crop(input_path, start, duration, out_path):
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", str(start)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd.append(out_path)
    subprocess.run(cmd, check=True)

    voc_cut = os.path.join(job_dir, "voc_cut.wav")
    inst_cut = os.path.join(job_dir, "inst_cut.wav")
    crop(vocal1, section1_start, section1_duration, voc_cut)
    crop(inst2, section2_start, section2_duration, inst_cut)

    # Adjust speed & pitch
    voc_final = os.path.join(job_dir, "voc_final.wav")
    inst_final = os.path.join(job_dir, "inst_final.wav")
    adjust_speed_and_pitch(voc_cut, voc_final, speed, pitch)
    adjust_speed_and_pitch(inst_cut, inst_final, speed, pitch)

    # Mix with volume control
    output_mp3 = os.path.join(job_dir, f"{job_id}.mp3")
    mix_cmd = [
        "ffmpeg", "-y",
        "-i", voc_final,
        "-i", inst_final,
        "-filter_complex",
        f"[0:a]volume={mix_volume}[a];[1:a]volume={1-mix_volume}[b];[a][b]amix=inputs=2:duration=first",
        output_mp3
    ]
    subprocess.run(mix_cmd, check=True)

    return {"download_url": f"/download/{job_id}/{job_id}.mp3"}

@app.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    path = os.path.join(OUTPUT_DIR, job_id, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="audio/mpeg", filename=filename)
