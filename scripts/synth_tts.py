# -*- coding: utf-8 -*-
import json, os, subprocess, pathlib

base_dir = pathlib.Path("/Users/fuxuepu/orca/projects/教学视频/word-drama/guzhuang_ep01_greeting")
lines_path = base_dir / "tts/lines.json"
out_dir = base_dir / "tts/v2_jenny"
out_dir.mkdir(parents=True, exist_ok=True)

with open(lines_path, "r", encoding="utf-8") as f:
    lines = json.load(f)

SR = 44100
TARGET_LUFS = -20.0

for name, text in lines:
    mp3_file = out_dir / f"{name}.mp3"
    wav_file = out_dir / f"{name}.wav"
    
    # 1. edge-tts synth
    cmd = ["uvx", "edge-tts", "--voice", "en-US-JennyNeural", "--text", text, "--write-media", str(mp3_file)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    
    # 2. convert to 44.1k stereo wav and normalize loudness to -20 LUFS
    # using loudnorm
    cmd_norm = [
        "ffmpeg", "-v", "error", "-y", "-i", str(mp3_file),
        "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,silenceremove=start_periods=1:start_duration=0.02:start_threshold=-50dB:stop_periods=1:stop_duration=0.08:stop_threshold=-50dB",
        "-ar", str(SR), "-ac", "2", str(wav_file)
    ]
    subprocess.run(cmd_norm, check=True)
    if mp3_file.exists():
        mp3_file.unlink()
        
    print(f"Generated {name:12s}: {text}")

# Generate _scene versions for in-scene dialogue
scene_names = ["q1", "q2", "q3", "q4", "q5"]
for s in scene_names:
    src_wav = out_dir / f"{s}.wav"
    dst_wav = out_dir / f"{s}_scene.wav"
    cmd_scene = [
        "ffmpeg", "-v", "error", "-y", "-i", str(src_wav),
        "-af", "apad=pad_dur=0.35,aecho=0.85:0.55:23|41|67:0.18|0.10|0.05,highpass=f=100,alimiter=limit=0.95",
        str(dst_wav)
    ]
    subprocess.run(cmd_scene, check=True)
    print(f"Generated scene version: {s}_scene.wav")

print("All Jenny TTS generated successfully in", out_dir)
