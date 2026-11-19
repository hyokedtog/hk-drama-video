#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""古装闲聊一集的后期：AI 小品片段 + 英文配音 + 字幕/英文大字/讲解侧卡 + 跟读词卡，按 cfg 的顺序拼成一集。

用法：python3 build.py <cfg.json> <输出.mp4> [只做第几项,逗号分隔]
cfg.items 依次是：
  clip：{"type":"clip","src":"ai/p1.mp4","range":[a,b],"room":[r0,r1],"mutes":[[a,b]],
         "hold":{"at":t,"d":秒},            # 在 t 处定格 d 秒（给英文配音腾地方）
         "en":[{"wav":"q1.wav","at":t,"text":"How are you doing?","pos":[x,y],"gain":0}],
         "subs":[{"t":[a,b],"text":"客官，里边请！"}],
         "panel":{"t":[a,b],"box":[x0,y0,x1,y1],"lines":[{"text":"are + [doing]","size":50,"color":"white","gap":20}]}}
  card：{"type":"card","bg":{"src":"ai/p2.mp4","at":t},"title":"跟着说","rows":[
         {"en":"I'm play[ing] games.","zh":"我在打游戏。","wav":"a_games.wav","times":1,"label":"现在"}]}
时间都是片段自己时间轴上的秒数。英文里 [..] 标黄、{..} 标红。本机 ffmpeg 没有 drawtext，字用 PIL 画成 PNG 再叠。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, SR = 1280, 720, 24, 44100
FONT_ZH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_EN = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
COL = {"white": (255, 255, 255), "soft": (226, 214, 190), "yellow": (255, 214, 64), "red": (255, 122, 92),
       "gold": (201, 164, 92), "dim": (150, 142, 128), "black": (0, 0, 0)}
LEAD, TAIL = 0.6, 0.9
CARD_GAIN = 0.0
EVENTS = {}          # 第几项 → [(这一项里的秒数, wav 名)]


def run(cmd):
    subprocess.run(cmd, check=True)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout.strip())


def is_cjk(ch):
    return ch >= "⺀"


def font_for(ch_is_cjk, size, bold=True):
    if ch_is_cjk:
        return ImageFont.truetype(FONT_ZH, int(size * 0.92), index=2 if bold else 0)
    return ImageFont.truetype(FONT_EN, size)


def parse(markup, base):
    """'I'm play[ing] games.' → [(文字, 颜色名)]；[..] 黄，{..} 红。"""
    out = []
    for m in re.finditer(r"\[([^\]]*)\]|\{([^}]*)\}|([^\[\]{}]+)", markup):
        if m.group(1) is not None:
            out.append((m.group(1), "yellow"))
        elif m.group(2) is not None:
            out.append((m.group(2), "red"))
        else:
            out.append((m.group(3), base))
    return out


def runs(markup, size, base, bold=True):
    """拆成同一种字体、同一种颜色的小段。"""
    res = []
    for text, color in parse(markup, base):
        buf, kind = "", None
        for ch in text:
            k = is_cjk(ch)
            if kind is None or k == kind or ch == " ":
                buf += ch
                kind = k if kind is None and ch != " " else kind
            else:
                res.append((buf, font_for(bool(kind), size, bold), color))
                buf, kind = ch, k
        if buf:
            res.append((buf, font_for(bool(kind), size, bold), color))
    return res


def rich_w(d, markup, size, bold=True):
    return sum(d.textlength(t, font=f) for t, f, _ in runs(markup, size, "white", bold))


def rich(d, x, y, markup, size, base="white", align="l", stroke=0, bold=True):
    """y 是基线。align: l 左对齐 / c 居中。返回右端 x。"""
    rs = runs(markup, size, base, bold)
    if align == "c":
        x -= sum(d.textlength(t, font=f) for t, f, _ in rs) / 2
    for t, f, c in rs:
        d.text((x, y), t, font=f, fill=COL[c], anchor="ls", stroke_width=stroke, stroke_fill=COL["black"])
        x += d.textlength(t, font=f)
    return x


def fit(d, markup, size, max_w, bold=True):
    while size > 20 and rich_w(d, markup, size, bold) > max_w:
        size -= 2
    return size


def blank():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def sub_png(text, out):
    img = blank()
    d = ImageDraw.Draw(img)
    size = fit(d, text, 46, W - 120)
    rich(d, W / 2, H - 58, text, size, "white", "c", stroke=5)
    img.save(out)


def en_png(item, out):
    """客商说的英文：小标签 + 黄色大字。"""
    img = blank()
    d = ImageDraw.Draw(img)
    x, y = item.get("pos", [50, 40])
    who = item.get("who", "客商")
    tf = font_for(True, 26)
    tw = d.textlength(who, font=tf)
    d.rounded_rectangle((x, y, x + tw + 24, y + 38), radius=7, fill=(0, 0, 0, 215))
    d.text((x + 12, y + 19), who, font=tf, fill=COL["yellow"], anchor="lm")
    size = fit(d, item["text"], item.get("size", 66), W - x - 40)
    rich(d, x, y + 50 + size * 0.78, item["text"], size, "yellow", "l", stroke=6)
    img.save(out)


def panel_png(p, out):
    """讲解时的侧卡：半透明深色底 + 细金边，里面几行字；高度按内容收。"""
    img = blank()
    d = ImageDraw.Draw(img)
    x0, y0, x1, _ = p["box"]
    lay, y = [], y0 + 30
    for ln in p["lines"]:
        if ln.get("rule"):
            y += ln.get("gap", 16)
            lay.append(("rule", y))
            y += 10
            continue
        size = fit(d, ln["text"], ln.get("size", 44), x1 - x0 - 72, ln.get("bold", True))
        y += ln.get("gap", 14) + size
        lay.append((ln, y, size))
    y1 = y + 34
    d.rectangle((x0, y0, x1, y1), fill=(18, 12, 8, 224), outline=COL["gold"], width=3)
    d.rectangle((x0 + 9, y0 + 9, x1 - 9, y1 - 9), outline=(120, 96, 52, 255), width=1)
    for it in lay:
        if it[0] == "rule":
            d.line((x0 + 36, it[1], x1 - 36, it[1]), fill=COL["gold"], width=2)
        else:
            ln, yy, size = it
            rich(d, x0 + 36, yy, ln["text"], size, ln.get("color", "white"), "l", bold=ln.get("bold", True))
    img.save(out)


def dark(frame_png):
    base = Image.open(frame_png).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(7))
    return Image.blend(base, Image.new("RGB", (W, H), (14, 9, 6)), 0.74).convert("RGBA")


def card_png(frame_png, card, lit, out):
    """跟读词卡：读到第 lit 行，前面的行留着（变暗），后面的行还没出来。"""
    img = dark(frame_png)
    d = ImageDraw.Draw(img)
    rows = card["rows"]
    n = len(rows)
    d.rectangle((36, 30, W - 36, H - 30), outline=COL["gold"], width=3)
    title = card.get("title", "")
    top = 64
    if title:
        rich(d, W / 2, 96, title, 36, "soft", "c", bold=False)
        d.line((W / 2 - 150, 116, W / 2 + 150, 116), fill=COL["gold"], width=2)
        top = 132
    avail = H - (96 if card.get("foot") else 56) - top
    row_h = min(card.get("row_h", 168), avail / n)
    y = top + (avail - row_h * n) / 2
    has_label = any(r.get("label") for r in rows)
    for i, r in enumerate(rows):
        if i > lit:
            break
        on = i == lit
        en_size = card.get("en_size", int(min(72, row_h * 0.46)))
        zh_size = int(min(46, row_h * 0.29))
        has_zh = bool(r.get("zh"))
        base_y = y + row_h * (0.52 if has_zh else 0.66)
        if has_label:
            lx, ex = 110, 400
            rich(d, lx, base_y, r.get("label", ""), int(en_size * 0.66), "yellow" if on else "dim", "l")
            en_size = fit(d, r["en"], en_size, W - ex - 80)
            rich(d, ex, base_y, r["en"], en_size, "white" if on else "dim", "l")
            if has_zh:
                rich(d, ex, base_y + zh_size + 14, r["zh"], zh_size, "soft" if on else "dim", "l", bold=False)
            if on:
                d.rectangle((70, y + row_h * 0.12, 78, y + row_h * 0.88), fill=COL["yellow"])
        else:
            en_size = fit(d, r["en"], en_size, W - 200)
            rich(d, W / 2, base_y, r["en"], en_size, "white" if on else "dim", "c")
            if has_zh:
                rich(d, W / 2, base_y + zh_size + 14, r["zh"], zh_size, "soft" if on else "dim", "c", bold=False)
            if on:
                w = rich_w(d, r["en"], en_size)
                d.polygon([(W / 2 - w / 2 - 44, base_y - en_size * 0.62), (W / 2 - w / 2 - 44, base_y - en_size * 0.08),
                           (W / 2 - w / 2 - 20, base_y - en_size * 0.35)], fill=COL["yellow"])
        y += row_h
    foot = card.get("foot")
    if foot and lit >= n - 1:
        rich(d, W / 2, H - 50, foot, 34, "soft", "c", bold=False)
    img.convert("RGB").save(out)


def grab(src, at, out):
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(src), "-frames:v", "1",
         "-vf", f"scale={W}:{H}", "-update", "1", str(out)])


def build_card(base, tts, work, k, card):
    frz = work / f"card_{k}_bg.png"
    grab(base / card["bg"]["src"], card["bg"]["at"], frz)
    t, events, stills = LEAD, [], []
    p0 = work / f"card_{k}_none.png"
    card_png(frz, card, -1, p0)
    stills.append([p0, LEAD])
    for i, r in enumerate(card["rows"]):
        wavs = r["wav"] if isinstance(r["wav"], list) else [r["wav"]]
        hold = 0.0
        for _ in range(r.get("times", 1)):
            for w in wavs:
                wd = dur(tts / w)
                events.append((tts / w, t + hold))
                hold += wd + 0.25
            hold += r.get("gap", max(1.3, sum(dur(tts / w) for w in wavs) + 0.5))   # 跟读空当
        p = work / f"card_{k}_{i}.png"
        card_png(frz, card, i, p)
        stills.append([p, hold])
        t += hold
    stills[-1][1] += TAIL
    total = t + TAIL
    EVENTS[k] = [(at, Path(w).name) for w, at in events]
    cmd, fc, n = ["ffmpeg", "-v", "error", "-y"], [], 0
    for png, dsec in stills:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dsec:.3f}", "-i", str(png)]
        n += 1
    fc.append("".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps={FPS},format=yuv420p[v]")
    cmd += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]
    labels = [f"[{n}:a]"]
    for j, (wav, at) in enumerate(events):
        cmd += ["-i", str(wav)]
        fc.append(f"[{n + 1 + j}:a]aresample={SR},volume={CARD_GAIN}dB,adelay={int(at * 1000)}:all=1[e{j}]")
        labels.append(f"[e{j}]")
    fc.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,alimiter=limit=0.85[a]")
    out = work / f"part_{k:02d}.mp4"
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "17",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-t", f"{total:.3f}", str(out)]
    run(cmd)
    print(f"[{k:02d}] 词卡「{card.get('title', '')}」{len(card['rows'])} 行，{total:.1f}s")
    return out


def build_clip(base, tts, work, k, c):
    src = str(base / c["src"])
    a, b = c["range"]
    hold = c.get("hold")
    hat, hd = (hold["at"], hold["d"]) if hold else (None, 0.0)

    def tm(t):                                   # 片段时间 → 这一小段成片里的时间
        return t - a + (hd if hat is not None and t > hat + 1e-6 else 0.0)

    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src]
    fc = []
    # 画面
    if hold:
        fc += [f"[0:v]trim={a:.3f}:{hat:.3f},setpts=PTS-STARTPTS,fps={FPS}[va]",
               f"[0:v]trim={hat:.3f}:{hat + 0.05:.3f},setpts=PTS-STARTPTS,fps={FPS},tpad=stop_mode=clone:stop_duration={hd:.3f},trim=0:{hd:.3f},setpts=PTS-STARTPTS[vh]",
               f"[0:v]trim={hat:.3f}:{b:.3f},setpts=PTS-STARTPTS,fps={FPS}[vb]",
               "[va][vh][vb]concat=n=3:v=1:a=0[v0]"]
    else:
        fc.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS,fps={FPS}[v0]")
    cur, n_in = "[v0]", 1
    fc.append(f"{cur}scale={W}:{H},setsar=1[v1]")
    cur = "[v1]"
    overlays = []
    for j, s in enumerate(c.get("subs", [])):
        png = work / f"clip_{k}_sub_{j}.png"
        sub_png(s["text"], png)
        overlays.append((png, tm(s["t"][0]), tm(s["t"][1])))
    for j, e in enumerate(c.get("en", [])):
        png = work / f"clip_{k}_en_{j}.png"
        en_png(e, png)
        st = tm(e["at"])
        overlays.append((png, st, st + dur(tts / e["wav"]) + e.get("linger", 0.5)))
    if c.get("panel"):
        panels = c["panel"] if isinstance(c["panel"], list) else [c["panel"]]
        for j, p in enumerate(panels):
            png = work / f"clip_{k}_panel_{j}.png"
            panel_png(p, png)
            overlays.append((png, tm(p["t"][0]), tm(p["t"][1])))
    for j, (png, t0, t1) in enumerate(overlays):
        cmd += ["-i", str(png)]
        fc.append(f"{cur}[{n_in}:v]overlay=0:0:enable='between(t,{t0:.3f},{t1:.3f})'[o{j}]")
        cur = f"[o{j}]"
        n_in += 1
    fc.append(f"{cur}format=yuv420p[v]")
    # 声音：先在原时间轴上静掉指定段，再剪、定格处垫底噪、贴英文
    chain = ["[0:a]asetnsamples=n=128"]
    for m0, m1 in c.get("mutes", []):
        chain.append(f"volume=eval=frame:volume='1-clip(min((t-{m0})/0.03,({m1}-t)/0.03),0,1)'")
    fc.append(",".join(chain) + f",aresample={SR}[am]")
    room = c.get("room")

    def room_tone(label, length):
        r0, r1 = room
        loops = int(length / (r1 - r0)) + 1
        size = int(round((r1 - r0) * SR))
        return (f"[0:a]aresample={SR},atrim={r0}:{r1},asetpts=PTS-STARTPTS,aloop=loop={loops}:size={size},atrim=0:{length:.3f},"
                f"afade=t=in:d=0.04,afade=t=out:st={max(length - 0.04, 0):.3f}:d=0.04[{label}]")

    if hold:
        fc += [f"[am]asplit=2[am1][am2]", f"[am1]atrim={a:.3f}:{hat:.3f},asetpts=PTS-STARTPTS[aa]",
               f"[am2]atrim={hat:.3f}:{b:.3f},asetpts=PTS-STARTPTS[ab]"]
        if room:
            fc.append(room_tone("ah", hd))
        else:
            fc.append(f"anullsrc=r={SR}:cl=stereo,atrim=0:{hd:.3f}[ah]")
        fc.append("[aa][ah][ab]concat=n=3:v=0:a=1[a0]")
    else:
        fc.append(f"[am]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a0]")
    labels = ["[a0]"]
    if room:
        for j, (m0, m1) in enumerate(c.get("mutes", [])):
            if m1 <= a or m0 >= b:
                continue
            fc.append(room_tone(f"rm{j}x", m1 - m0))
            fc.append(f"[rm{j}x]adelay={int(max(tm(m0), 0) * 1000)}:all=1[rm{j}]")
            labels.append(f"[rm{j}]")
    for j, e in enumerate(c.get("en", [])):
        cmd += ["-i", str(tts / e["wav"])]
        fc.append(f"[{n_in}:a]aresample={SR},volume={e.get('gain', 0)}dB,adelay={int(tm(e['at']) * 1000)}:all=1[en{j}]")
        labels.append(f"[en{j}]")
        n_in += 1
    total = b - a + hd
    EVENTS[k] = [(tm(e["at"]), e["wav"]) for e in c.get("en", [])]
    fc.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,volume={c.get('gain', 0)}dB,"
              f"afade=t=in:d=0.05,afade=t=out:st={total - 0.08:.3f}:d=0.08,alimiter=limit=0.85[a]")
    out = work / f"part_{k:02d}.mp4"
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "17",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-t", f"{total:.3f}", str(out)]
    run(cmd)
    print(f"[{k:02d}] 片段 {c['src']} {a:.2f}–{b:.2f}" + (f" 定格 {hd:.2f}s" if hold else "") + f"，{total:.1f}s")
    return out


def build(cfg_path, out, only=None):
    global CARD_GAIN
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    CARD_GAIN = cfg.get("card_gain", 0.0)
    base = Path(cfg_path).parent
    tts = base / cfg["tts"]
    work = base / "_work" / Path(cfg_path).stem
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for k, item in enumerate(cfg["items"]):
        p = work / f"part_{k:02d}.mp4"
        if only is not None and k not in only and p.exists():
            parts.append(p)
            continue
        parts.append(build_card(base, tts, work, k, item) if item["type"] == "card" else build_clip(base, tts, work, k, item))
    ins, fc = [], ""
    for k, p in enumerate(parts):
        ins += ["-i", str(p)]
        fc += f"[{k}:v][{k}:a]"
    fc += f"concat=n={len(parts)}:v=1:a=1[v][a0];[a0]volume={cfg.get('master_gain', -1.5)}dB[a]"
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    t, timeline = 0.0, []
    for k, p in enumerate(parts):
        d_ = dur(p)
        print(f"  {t:6.1f}s  [{k:02d}] {cfg['items'][k]['type']} {cfg['items'][k].get('note', '')}")
        timeline.append({"k": k, "start": round(t, 3), "dur": round(d_, 3), "type": cfg["items"][k]["type"], "note": cfg["items"][k].get("note", ""),
                         "en": [[round(t + at, 3), w] for at, w in EVENTS.get(k, [])]})
        t += d_
    if only is None:
        json.dump(timeline, open(str(out) + ".timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("成片", out, f"{dur(out):.1f}s")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    only = {int(x) for x in sys.argv[3].split(",")} if len(sys.argv) > 3 else None
    build(sys.argv[1], sys.argv[2], only)
