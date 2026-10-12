---
name: kewei-jianying
description: 用可为AI开源剪映字幕模板，把字幕(SRT)或口播稿一键生成可在剪映专业版里继续编辑的草稿。当用户提到“剪映草稿”“剪映模板”“字幕模板”“可为AI模板”“把口播稿/字幕做成剪映工程”时使用。
compatibility: Windows / macOS，Python 3.9+，剪映专业版（草稿格式为非官方格式，基于开源项目 pyJianYingDraft 0.3）
agent_created: true
---

# 可为AI 剪映字幕模板（kewei-jianying）

目标：在用户电脑本地生成一个剪映草稿，用户打开剪映就能在草稿列表里看到并接着改。全程只在本机运行，不上传任何文件。

## 第 1 步：检查 CLI 是否已安装

运行：

```bash
kewei-jianying --version
```

- 输出 `kewei-jianying 0.3.x` 或更高 → 跳到第 3 步。
- 提示找不到命令 → 第 2 步。

## 第 2 步：安装 CLI（按顺序尝试，成功一个就停）

```bash
uv tool install "git+https://github.com/ffzhen/kewei-jianying-templates"
pipx install "git+https://github.com/ffzhen/kewei-jianying-templates"
python3 -m pip install --user "git+https://github.com/ffzhen/kewei-jianying-templates"   # Windows 用 py -m pip
```

- 都没有 uv/pipx 时，可先 `python3 -m pip install --user uv`。
- 访问 GitHub 失败时告诉用户：可以开代理，或下载仓库 zip 解压后在目录里执行 `python3 -m pip install --user .`。
- pip 方式装完仍找不到命令时，用 `python3 -m kewei_jianying` 代替 `kewei-jianying`。
- 装完再次运行 `kewei-jianying --version` 确认。

## 第 3 步：环境自检（自动找剪映草稿目录）

```bash
kewei-jianying doctor --json
```

- CLI 会按顺序自动找剪映草稿目录：环境变量 → 剪映/CapCut 设置里的「草稿位置」→ 默认目录 → 扫描常见位置（取最近有草稿的）。**不要问用户路径**，直接继续。
- 只有 `ok: false` 且草稿目录为空时：运行 `kewei-jianying where` 把候选列表给用户看，请用户打开剪映「设置 → 草稿位置」确认路径，之后每条命令加 `--draft-root "<路径>"`。
- 没装剪映：提示用户先安装剪映专业版并至少打开一次。

## 第 4 步：选模板

```bash
kewei-jianying list
```

| 模板 id | 适合 |
|---|---|
| zhishi-koubo | 知识口播、专家 IP（白字 + 金黄关键词） |
| keji-jiexi | AI / 数码 / 科技解读 |
| mendian-zhongcao | 门店、餐饮、生活方式种草 |
| shangwu-zhuanye | 律师、财税、B2B 专业内容 |

用户没指定就按内容选最贴近的一个，并说明理由。动效默认用模板自带的，用户想换再用 `--motion <id>`（`list` 里有 30 种，`none` 表示不加）。

## 第 5 步：准备输入并生成草稿

1. 字幕来源（二选一）：
   - 用户有 SRT 字幕 → `--srt <文件>`
   - 只有口播稿 → 存成 txt，用 `--text-file <文件>`（按标点切句、按语速估算时长，之后在剪映里对齐配音）
2. 关键词：从字幕里挑 3–8 个最重要的词（必须是原文里出现的词），用 `-k "词1,词2"`。
3. 标题：一句 8–16 字的标题，`--title`。
4. 可选素材：口播视频 `--video`、配音 `--audio`、背景音乐 `--bgm`（会复制到草稿目录里）。
5. 草稿名：`-n <名字>`（不能含 / \\ : * ? 等符号）。同名已存在时换个名字；只有用户明确同意才加 `--replace`（旧草稿会备份到草稿目录的 .kewei-replaced/）。

草稿会先在临时目录生成，再自动放进剪映草稿目录，不需要你手动复制。

```bash
kewei-jianying build -t zhishi-koubo --srt input.srt -k "剪辑,持续输出" --title "把字幕模板交给Agent" -n 我的第一条草稿 --json
```

## 第 6 步：交付

读取 `--json` 输出，告诉用户：

- 草稿名和位置（`draft_dir`），以及草稿目录是怎么找到的（`found_by`）；
- 打开剪映专业版 → 首页草稿列表找到同名草稿；
- 没看到：完全退出剪映（Mac 用 Cmd+Q）再打开；
- 如果 `index_registered` 为 false 且 `index_reason` 提到「正在运行」：请用户先完全退出剪映，然后你运行 `kewei-jianying register <草稿名>`，再让用户打开剪映；
- 有 `warning` 字段时原样转告；
- 字体、动画首次打开时剪映可能需要联网下载，看到“加载失败”多等一会儿或重开草稿。

如果 `ok: false`，把 `error` 原文告诉用户并按提示处理，不要编造成功结果。

## 注意

- 只读写用户指定的文件和剪映草稿目录；不要删除已有草稿。
- 剪映草稿是非官方格式，剪映大版本更新后可能需要 `uv tool upgrade kewei-jianying`（或重新安装）。
- 需要批量出片、选题脚本、团队定制模板：可为AI https://keweiai.cn/
