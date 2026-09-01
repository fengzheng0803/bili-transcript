# bili-transcript

B 站视频 → 结构化 markdown 的 Claude Code 技能：字幕优先、Whisper 转写兜底、LLM 全文整理。

## 能力

- 输入 BV 号 / 视频链接 / b23.tv 短链（或按视频名搜索确认）
- 优先读取 B 站现成中文字幕（含 AI 字幕），无字幕时下载音频流走本地 faster-whisper 或云端 ASR 转写
- 转写完成后脚本**直调 LLM**（不经代理转发）：全文一次输入，划分章节、归纳标题、剔除广告/寒暄/无关内容，产出结构化 markdown
- 未配置 LLM 或加 `--no-structure` 时只产出带时间戳的原始文字稿

## 安装

把本目录复制到项目的 `.claude/skills/bili-transcript`，然后：

```bash
bash scripts/setup.sh   # 初始化依赖（ffmpeg、Python venv、faster-whisper）
cp config.example.json 项目根目录/config.json
```

## 配置

`config.json`（放在**项目根目录**，不随仓库分发）：

| 块 | 说明 |
|---|---|
| `bilibili.cookie` | 可选；无 cookie 时多数视频走转写路线（B 站对匿名不返回字幕列表） |
| `asr.cloud` | OpenAI 兼容 ASR（如硅基流动 SenseVoiceSmall）；`asr.default` 可切 `local` |
| `asr.local` | faster-whisper 模型大小 / 设备 |
| `llm` | OpenAI 兼容 chat 服务（如 DeepSeek 官方）；不配 `api_key` 则不跑语义阶段 |

## 使用

在项目根目录运行：

```bash
~/bilibili-dep/venv-bilibili/bin/python .claude/skills/bili-transcript/scripts/main.py BV1xxxxxx [--page N] [--asr local|cloud] [--no-structure]
```

产出：

- `transcripts/<标题>-<bvid>.md` —— 最终结构化文档（视频信息表 + LLM 整理的章节正文）
- `.cache/bili-transcript/<bvid>-pN/transcript.txt` —— 原始转写文字稿
- `.cache/bili-transcript/<bvid>-pN/structured.md` —— LLM 原始输出缓存（重跑零花费）

## 测试

```bash
~/bilibili-dep/venv-bilibili/bin/python -m pytest tests/
```
