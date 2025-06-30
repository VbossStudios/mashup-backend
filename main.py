from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from utils.separate import separate_stems
from utils.mixer import mix_audio
import os
import uuid

app = FastAPI()

@app.post("/mashup/")
async def create_mashup(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    vocals_from: int = Form(1)
):
    uid = str(uuid.uuid4())
    base_dir = f"tmp/{uid}"
    os.makedirs(base_dir, exist_ok=True)

    file1_path = f"{base_dir}/song1.wav"
    file2_path = f"{base_dir}/song2.wav"
    with open(file1_path, "wb") as f:
        f.write(await file1.read())
    with open(file2_path, "wb") as f:
        f.write(await file2.read())

    song1_vocals, song1_instr = separate_stems(file1_path, base_dir, "song1")
    song2_vocals, song2_instr = separate_stems(file2_path, base_dir, "song2")

    if vocals_from == 1:
        mix_path = mix_audio(song1_vocals, song2_instr, f"{base_dir}/mashup.wav")
    else:
        mix_path = mix_audio(song2_vocals, song1_instr, f"{base_dir}/mashup.wav")

    return FileResponse(mix_path, media_type="audio/wav", filename="mashup.wav")
