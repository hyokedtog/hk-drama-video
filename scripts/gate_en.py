# -*- coding: utf-8 -*-
"""成片门禁：把成片里每一句英文按时间表重新切出来（窄切、宽切各一次），两个模型听写，和台本比。
用法：uv run --with mlx-whisper python -I gate_en.py 成片.mp4"""
import json, os, re, subprocess, sys, tempfile
import mlx_whisper
mp4 = sys.argv[1]
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
text = {n: t for n, t in json.load(open(os.path.join(base, "tts/lines.json"), encoding="utf-8"))}
tl = json.load(open(mp4 + ".timeline.json", encoding="utf-8"))
norm = lambda s: re.sub(r"[^a-z]", "", s.lower())
def dur(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)
tmp = tempfile.mkdtemp()
bad, n = [], 0
for item in tl:
    for at, w in item["en"]:
        name = w.replace("_scene", "").replace(".wav", "")
        d = dur(os.path.join(base, "tts/final", w.replace("_scene", "")))
        for kind, a, b in (("窄", at - 0.06, at + d + 0.12), ("宽", at - 0.30, at + d + 0.22)):
            seg = os.path.join(tmp, "s.wav")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(a, 0):.3f}", "-to", f"{b:.3f}", "-i", mp4, "-ac", "1", "-ar", "16000", seg], check=True)
            for repo in ("mlx-community/whisper-large-v3-turbo", "mlx-community/whisper-small.en-mlx"):
                r = mlx_whisper.transcribe(seg, path_or_hf_repo=repo, language="en")["text"].strip()
                n += 1
                if norm(r) != norm(text[name]):
                    bad.append(f"{at:6.1f}s [{item['k']:02d} {item['note']}] {kind}切 {'large' if 'large' in repo else 'small'}：要「{text[name]}」听成「{r}」")
print(f"共 {sum(len(i['en']) for i in tl)} 句英文、{n} 次听写，不对的 {len(bad)} 处")
print("\n".join(bad))
