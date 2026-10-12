# SPDX-License-Identifier: Apache-2.0
"""SRT 解析与多片段字幕切分/时间计算。

切分与时间规则移植自 Tigenix 平台 subtitle_packaging.SubtitlePackager
（split_subtitle_simple / calculate_segment_timing 的「重叠显示」模式）。
开源版没有 ASR 单字时间戳，因此按字数比例估算每个片段的出现时间。
"""
import re
from pathlib import Path
from typing import Dict, List, Sequence

PUNCT = "，,。！!？?；;：:、 "


def _ts(x: str) -> float:
    h, m, rest = x.strip().replace(".", ",").split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: str) -> List[Dict]:
    items = []
    text = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    for block in re.split(r"\n\s*\n", text):
        lines = block.strip().splitlines()
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None or idx + 1 >= len(lines):
            continue
        a, b = lines[idx].split("-->")
        t = "".join(lines[idx + 1:]).strip()
        if t:
            items.append({"start": _ts(a), "end": _ts(b), "text": t})
    if not items:
        raise ValueError(f"SRT 里没有解析到字幕：{path}")
    return items


def text_to_captions(text: str, cps: float = 4.5) -> List[Dict]:
    """没有 SRT 时：把口播稿按标点切句，按每秒 cps 字估算时长（之后可在剪映里对齐配音）。"""
    parts = [p.strip() for p in re.split(r"[\n。！!？?；;]+", text) if p.strip()]
    out, t = [], 0.0
    for p in parts:
        d = max(1.2, len(p) / cps)
        out.append({"start": round(t, 3), "end": round(t + d, 3), "text": p})
        t += d
    return out


def split_positions(text: str, n: int, keywords: Sequence[str] = ()) -> List[int]:
    """返回 n-1 个切分点。优先在关键词前切（让关键词落在高亮片段），其次在标点处，最后按字数均分。"""
    if n <= 1 or len(text) < n * 2:
        return []
    for k in keywords:
        i = text.find(k) if k else -1
        if n == 2 and i > 1:
            return [i]
    cuts = [i + 1 for i, ch in enumerate(text[:-1]) if ch in PUNCT and 1 < i + 1 < len(text) - 1]
    if len(cuts) >= n - 1:
        targets = [len(text) * j / n for j in range(1, n)]
        chosen = sorted({min(cuts, key=lambda c: abs(c - t)) for t in targets})
        if len(chosen) == n - 1:
            return chosen
    return [round(len(text) * j / n) for j in range(1, n)]


def split_caption(cap: Dict, n: int, keywords: Sequence[str] = ()) -> List[Dict]:
    """重叠显示：每个片段在前一片段「语音结束」时出现，并一直显示到整条字幕结束。"""
    text = cap["text"]
    pos = split_positions(text, n, keywords)
    if not pos:
        return [dict(cap)]
    bounds = [0] + pos + [len(text)]
    dur = cap["end"] - cap["start"]
    out = []
    for j in range(len(bounds) - 1):
        seg_text = text[bounds[j]:bounds[j + 1]].strip(PUNCT) or text[bounds[j]:bounds[j + 1]]
        start = cap["start"] + dur * bounds[j] / len(text)
        out.append({"start": round(start, 3), "end": cap["end"], "text": seg_text})
    return out
