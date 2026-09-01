---
name: bili-transcript
description: 读取 Bilibili（B站）视频内容转为文字稿。当用户提到 bilibili/B站 视频（BV 号、视频链接、b23.tv 短链或视频名）并想看内容、做总结、提取字幕或转写时使用。优先读取现成中文字幕（含 AI 字幕），无字幕时下载音频流用本地 Whisper 或云端 API 转写，随后脚本直调 LLM 把全文整理为结构化 markdown 文档。
---

# Bili Transcript

## 触发与入口

- 用户输入含 `BV` 号 → 直接处理
- 输入是链接（含 b23.tv 短链）→ 脚本自动解析出 BV 号
- 只有视频名/关键词 → 先运行 `search` 子命令，把候选列表反馈给用户确认，用户选定后再处理

## 执行步骤

1. 确定 bvid（必要时先搜索确认）。
2. 运行（首次使用前先运行 `bash scripts/setup.sh` 初始化依赖）：
   （在项目根目录下运行；config.json 与 .cache 缓存都相对项目根）

   ```
   ~/bilibili-dep/venv-bilibili/bin/python scripts/main.py <bvid> [--page N] [--asr local|cloud] [--no-structure]
   ```

3. 转写完成后，脚本在**已配置 `llm.api_key` 时自动运行语义阶段**：把全文文字稿一次发给 LLM，由 LLM 划分章节、归纳标题、剔除广告/寒暄/无关内容，脚本补上视频信息表头后直接产出结构化文档 `transcripts/<标题>-<bvid>.md`；未配置 LLM 或加 `--no-structure` 则只产出原始文字稿 `.cache/bili-transcript/<bvid>-p<N>/transcript.txt`。
4. 读取脚本输出提示的文档路径即可交付。**代理不参与正文整理**；LLM 调用由脚本直发，失败会打印 `[语义缺失]` 且不产 md（可重跑）。LLM 原始输出缓存在 cache 目录 `structured.md`，重跑不会重复花钱。

## 输出文档结构

- 一级标题：视频标题
- 「视频信息」表格：BV号 / up主 / 时长 / 字幕来源
- 正文：由 LLM 整理——按主题分章节、归纳标题、保留时间戳，广告与无关内容被剔除
- 保存：项目根 `transcripts/<标题>-<bvid>.md`（标题清洗掉 `/\:*?"<>|` 等非法字符）

## 转写路线

- 默认云路线：硅基流动免费 ASR（`FunAudioLLM/SenseVoiceSmall`）；`--asr local` 切换本地 faster-whisper
- 云路线需配置 `api_key`：把 `config.example.json` 复制为 `config.json` 填入，或设环境变量 `BILI_ASR_API_KEY`（免费申请：https://cloud.siliconflow.cn/account/ak ）
- 本地路线首次运行自动下载模型到 `~/bilibili-dep/models`（medium 约 1.5GB）

## 语义阶段配置（可选）

- 在 `config.json` 的 `llm` 块填任意 OpenAI 兼容服务的 `base_url` / `api_key` / `model`（如 DeepSeek 官方：`https://api.deepseek.com` + `deepseek-chat`；也可设环境变量 `BILI_LLM_API_KEY` 等）
- 超长视频（文字稿超 5 万字符）自动按两半切分依次调用再拼接

## 常见问题

- 视频需要登录（番剧/充电专属/大会员）→ 在 `config.json` 的 `bilibili.cookie` 填浏览器 Cookie（F12 → 网络请求 → 复制 Cookie 头），或设 `BILI_COOKIE`
- 分P 视频默认处理 P1，`--page N` 指定其他页码
- 无 cookie 时多数视频走转写路线（B站对匿名不返回字幕列表），在 `config.json` 配置 `bilibili.cookie` 可优先使用免费字幕
- 语义阶段想要不同模型（更便宜/更贵）→ 改 `config.json` 的 `llm.model`；不想花钱 → 不配 `llm.api_key` 或加 `--no-structure`
- 整理效果不满意 → 删除 cache 目录里的 `structured.md` 重跑（会重新调用 LLM）；提示词在 `scripts/semantic/llm.py` 的 `SYSTEM_PROMPT`
