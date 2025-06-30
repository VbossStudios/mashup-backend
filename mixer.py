from pydub import AudioSegment

def mix_audio(vocal_path, instr_path, output_path):
    vocals = AudioSegment.from_file(vocal_path)
    instr = AudioSegment.from_file(instr_path)
    mixed = instr.overlay(vocals)
    mixed.export(output_path, format="wav")
    return output_path
