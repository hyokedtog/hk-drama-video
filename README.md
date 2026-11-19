# hk-drama-video

港风 / 古装年代剧质感 AI 短剧视频生成 Skill。

本项目凝练了基于 **TapNow / Seedance 视频生成模型 + 自动化音频与 FFmpeg 流水线 + Whisper 双模型听写门禁** 的完整教学短视频工程闭环。

---

## 🌟 核心特色

1. **经典年代剧质感**：沉淀经过多轮实测验证的 80/90 年代港剧、古装武侠片光影与布景提示词架构。
2. **拒绝机械电音**：避开过度算法变调与滤波破坏，采用高保真纯正发音教学级音色，搭配场景声学混响反射。
3. **精准控时与防穿帮**：单镜头字数限制、人物防融合理念、遮嘴发音设计，确保生成成功率。
4. **自动化装配流水线**：单行命令将小品片段、动态逐行高亮跟读词卡、字幕与音效无缝混剪输出。
5. **双模型听写门禁**：集成 Whisper-large-v3-turbo 与 Whisper-small 自动化双轨听写，杜绝发音与文字缺陷。

---

## 📁 目录结构

```
hk-drama-video/
├── SKILL.md                  # Skill 完整规范与核心实操经验
├── README.md                 # 仓库说明文档
├── scripts/
│   ├── synth_tts.py          # 纯正英语发音批量生成与 -20 LUFS 标准化
│   ├── build_video.py        # FFmpeg 全自动化成片混合组装脚本
│   └── gate_en.py            # Whisper 双模型成片发音听写门禁
└── templates/
    ├── cfg_template.json     # 成片剪辑工程模板（支持多卡、画中画、高亮跟读）
    └── lines_template.json   # 词汇与教学对话台本配置模板
```

---

## 🚀 快速上手

### 环境准备

- Python 3.9+
- [FFmpeg](https://ffmpeg.org/)
- [uv](https://github.com/astral-sh/uv) (推荐)

### 使用步骤

1. **准备台词与分镜**：在 `templates/lines_template.json` 中配置需要教学的外语或台词。
2. **合成标准发音**：
   ```bash
   python3 scripts/synth_tts.py
   ```
3. **渲染最终成片**：
   ```bash
   python3 scripts/build_video.py templates/cfg_template.json out/成片.mp4
   ```
4. **运行双模型听写验收**：
   ```bash
   uv run --with mlx-whisper python -I scripts/gate_en.py out/成片.mp4
   ```

---

## 📜 许可证

MIT License.
