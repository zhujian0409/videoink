# videoink

[![ci](https://github.com/zhujian0409/videoink/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/zhujian0409/videoink/actions/workflows/ci.yml)
[![license](https://img.shields.io/github/license/zhujian0409/videoink)](./LICENSE)

**语言：** [English](./README.md) | 中文

> 把任何视频链接变成一篇打磨过的 Markdown 文章。**在 Claude Code 里用它零 API 开销** —— 也可作为独立 CLI（需要你自己的 LLM key）。

**状态：** v0.3 alpha。端到端跑通。支持四种 LLM provider（OpenAI / Anthropic / OpenRouter / Ollama）。暂未发 PyPI —— 先从 git 装（见下）。

贴一个 YouTube、B 站或任何 yt-dlp 支持的视频 URL。`videoink` 会拉音频、做转写（本地或 OpenAI Whisper），产出一篇可直接发布的 Markdown 文章和完整本地产物。想发到哪随你 —— Substack、Ghost、dev.to、Medium、Obsidian、你自己的站点……

## 两种用法

| 模式 | 转写步骤 | 写文章步骤 | 外部 API 开销 |
|---|---|---|---|
| **Claude Code skill**（推荐） | 本地 `faster-whisper` | Claude Code 自己写 | **0 元** |
| 独立 CLI | 本地 `faster-whisper` 或 OpenAI Whisper | OpenAI / Anthropic API | 按次计费（一般 < $0.10） |

skill-native 是主推模式 —— 所有东西留在你本机，凭证不外流。

## 为什么要做这个

Cast Magic、Podsqueeze 这类闭源 SaaS 做的事差不多，但：

- 锁死你只能用它家的 LLM 和定价。
- 转写和草稿都跑在他们云上。
- 没法跑在 Ollama 或离线环境。

`videoink` = 一个 pip 包 + 一个 Claude Code skill。想用 OpenAI / Anthropic 就带上自己的 key（**仅 CLI 模式需要**）；Claude Code 用户**一把 key 都不需要**。

## Quickstart —— Claude Code skill 模式（零 API）

```bash
# 装上时带 local extra，任何 API key 都不用
pip install 'git+https://github.com/zhujian0409/videoink.git#egg=videoink[local]'
```

然后在 Claude Code 里贴视频 URL，说"帮我把这个视频写成文章"。skill 会：

1. 用 `yt-dlp` 下载音频
2. 用 `faster-whisper` 离线转写（首次会从 Hugging Face 下 ~145 MB 的 base 模型）
3. Claude Code 本身读 transcript 并直接写 `article.md`

产物统一放在 `./output/<video-id>/`。

## Quickstart —— 独立 CLI 模式（需要 API key）

```bash
# 同时装 openai 和 local extra（local 默认用来做转写）
pip install 'git+https://github.com/zhujian0409/videoink.git#egg=videoink[openai,local]'

# 设置一个 provider key
export OPENAI_API_KEY=sk-...           # 或 ANTHROPIC_API_KEY=sk-ant-...

# 跑整个 pipeline
videoink full https://www.youtube.com/watch?v=<id> --engine local
```

去掉 `--engine local` 可切 OpenAI Whisper；加 `--provider anthropic` 让 generate 走 Claude。

## 你会拿到什么

```
./output/<video-id>/
    article.md                  # 可发布的 Markdown 文章
    transcript.json             # Whisper 完整输出（segments / 时间戳 / 语言）
    transcript.txt              # 纯文本转写
    images/                     # v0.1 留空；v0.2 会填图
    <title> [<id>].audio.m4a    # 转写用的音频
```

用任何 Markdown 编辑器打开 `article.md`，从那里发布。

## 前置条件

- Python 3.10+
- `ffmpeg` 在 PATH（yt-dlp 需要）
- **Claude Code skill 模式**：无需其他（首次运行会下 `faster-whisper` base 模型，~145 MB）
- **独立 CLI 模式**：`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` 至少一个

## 子命令

| 命令 | 做什么 |
|---|---|
| `videoink probe <url>` | 列出所有可下载格式 / dump extractor JSON |
| `videoink fetch <url> --mode audio` | 只下音频 |
| `videoink transcribe <audio> --engine local` | 离线 faster-whisper → `transcript.{json,txt}` |
| `videoink transcribe <audio> --engine openai` | OpenAI Whisper API（25 MB 上限） |
| `videoink generate <transcript.json>` | transcript + style → `article.md`（需要 LLM key；**Claude Code 模式下不用**） |
| `videoink full <url>` | 一次跑完四步（CLI 模式用） |

所有子命令都接受 `--help`。

## 文章风格

内置两种风格（作为 package data 打包随 pip 带上）：

- `default` — 通用博客 / newsletter 语气
- `technical` — 技术向、面向开发者

也可以自己加：

```bash
videoink full <url> --style mystyle --styles-dir ./my-styles/
# 会读 ./my-styles/mystyle.md
```

在 Claude Code 模式里，直接告诉 assistant 用哪个 style 文件即可。

## Claude Code skill

repo 根的 [`SKILL.md`](./SKILL.md) 是 Claude Code 读的 skill 定义文件。它编码了三步 skill-native 工作流（fetch → local transcribe → assistant 自己写），并明确告诉 Claude **不要** 在 skill 模式下调 `videoink generate` —— 避免多开一条不必要的 LLM 计费通道。

## Roadmap

见 [`ROADMAP.md`](./ROADMAP.md)。简版：

- **v0.1** ✓ — 5 个 CLI 子命令、local + OpenAI 两种转写引擎、OpenAI + Anthropic LLM providers、Claude Code skill、skill-native 零 API 模式。
- **v0.2** — OpenRouter + Ollama providers、多模型 judge loop、B 站一等公民支持、超 25 MB 音频自动分段、网络图片抓取。
- **v0.3+** — Codex / Cursor / 其他 agent skill 适配器、可选 HTTP API。

## 项目背景

这个仓库脱胎自作者用了三周的私人自动化 pipeline（每天把新闻视频转成长文章）。开源时剥离了平台相关的发布代码，prompts 改为英文默认，LLM 后端做成可插拔，输出纯 Markdown 让用户自己决定发布渠道。

## 贡献

`ROADMAP.md` 有 v0.2 backlog，都是具体、小范围的任务。欢迎 PR。

## License

[MIT](./LICENSE)
