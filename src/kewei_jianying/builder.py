# SPDX-License-Identifier: Apache-2.0
# 基于 pyJianYingDraft (https://github.com/GuanYixuan/pyJianYingDraft, Apache-2.0)，见仓库 NOTICE。
"""字幕模板 + 字幕 + 关键词 (+ 可选素材) → 剪映草稿文件夹。"""
import copy
import json
import os
from importlib import resources
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pyJianYingDraft as draft
from pyJianYingDraft import TrackType, trange

import shutil
import tempfile

from . import draft_utils, paths, place, subtitles


# ---------- 模板 ----------
def _pkg_dir():
    return resources.files(__package__)


def list_templates() -> List[Dict]:
    out = []
    for d in sorted((_pkg_dir() / "templates").iterdir(), key=lambda p: p.name):
        f = d / "template.json"
        if f.is_file():
            out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def load_template(tid: str) -> Dict:
    p = Path(tid)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    for t in list_templates():
        if t["id"] == tid or t["name"] == tid:
            return t
    raise KeyError(f"未知模板：{tid}。可用：{', '.join(t['id'] for t in list_templates())}")


def list_motions() -> Dict[str, Dict]:
    return json.loads((_pkg_dir() / "motions.json").read_text(encoding="utf-8"))["motions"]


# ---------- 文本 ----------
class HighlightTextSegment(draft.TextSegment):
    """TextSegment + 关键词分段高亮（剪映多样式文本）。"""

    def __init__(self, *a, highlights=None, **kw):
        super().__init__(*a, **kw)
        self.highlights = highlights or []

    def export_material(self):
        ret = super().export_material()
        if not self.highlights:
            return ret
        content = json.loads(ret["content"])
        base = content["styles"][0]
        styles, cur = [], 0
        for s, e, color, size, bold in sorted(self.highlights):
            if s < cur:
                continue
            if s > cur:
                seg = copy.deepcopy(base); seg["range"] = [cur, s]; styles.append(seg)
            hl = copy.deepcopy(base); hl["range"] = [s, e]
            hl["fill"]["content"]["solid"]["color"] = list(color)
            hl["size"], hl["bold"] = size, bold
            styles.append(hl); cur = e
        if cur < len(self.text):
            seg = copy.deepcopy(base); seg["range"] = [cur, len(self.text)]; styles.append(seg)
        content["styles"] = styles
        ret["content"] = json.dumps(content, ensure_ascii=False)
        return ret


def _hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _font(name: Optional[str]):
    if not name:
        return None
    if name in draft.FontType.__members__:
        return draft.FontType[name]
    key = name.lower().replace(" ", "").replace("_", "").replace("-", "")
    for m in draft.FontType:  # 按剪映界面显示名模糊匹配（移植自 Tigenix _resolve_font_type）
        if getattr(m.value, "name", "").lower().replace(" ", "") == key:
            return m
    return None


def _parts(style: Dict, color=None, size_mul: float = 1.0):
    b = style["base_style"]
    st = draft.TextStyle(size=b["size"] * size_mul, bold=b["bold"], color=tuple(color or b["color"]), align=b["align"],
                         auto_wrapping=b["auto_wrapping"], max_line_width=b["max_line_width"],
                         line_spacing=b.get("line_spacing", 0))
    sh = style.get("shadow_style")
    shadow = sh and draft.TextShadow(alpha=sh["alpha"], color=tuple(sh["color"]), diffuse=sh["diffuse"],
                                     distance=sh["distance"], angle=sh["angle"])
    bg = style.get("background_style")
    background = bg and draft.TextBackground(color=bg["color"], style=bg.get("style", 1), alpha=bg["alpha"],
                                             round_radius=min(float(bg.get("round_radius", 0)), 1.0),
                                             height=bg["height"], width=bg["width"],
                                             horizontal_offset=bg["horizontal_offset"], vertical_offset=bg["vertical_offset"])
    return st, _font(b.get("font_type")), shadow, background


def _highlights(text: str, kws: Sequence[str], hl: Dict):
    out = []
    for k in kws:
        i = text.find(k) if k else -1
        if i >= 0:
            out.append((i, i + len(k), tuple(hl["color"]), hl["size"], hl["bold"]))
    return out


def _intro(name: Optional[str]):
    return draft.TextIntro[name] if name and name in draft.TextIntro.__members__ else None


def _add_text(script, seg, track):
    """pyJianYingDraft 0.3 给文本片段引用了 speed 素材却不写入 materials.speeds；剪映自己的草稿里文本也有 speed，这里补上。"""
    script.add_segment(seg, track)
    if seg.speed not in script.materials.speeds:
        script.materials.speeds.append(seg.speed)


# ---------- 构建 ----------
def build(template: str, *, srt: Optional[str] = None, text: Optional[str] = None, keywords: Sequence[str] = (),
          title: str = "", name: str = "kewei-draft", draft_root: Optional[str] = None, motion: Optional[str] = None,
          video: Optional[str] = None, audio: Optional[str] = None, bgm: Optional[str] = None,
          replace: bool = False, register: bool = True) -> Dict:
    cfg = load_template(template)
    if srt:
        caps = subtitles.parse_srt(srt)
    elif text:
        caps = subtitles.text_to_captions(text)
    else:
        raise ValueError("需要 --srt 或 --text 之一")
    det = paths.detect(draft_root)
    root = det["path"]
    if not root:
        raise FileNotFoundError("找不到剪映草稿目录：运行 kewei-jianying where 查看候选，或用 --draft-root 指定（剪映 设置 → 草稿位置）")
    place.validate_name(name)
    os.makedirs(root, exist_ok=True)
    if os.path.exists(os.path.join(root, name)) and not replace:
        raise FileExistsError(f"草稿「{name}」已存在：{os.path.join(root, name)}（换个 --name，或加 --replace 覆盖，旧草稿会备份）")
    # 先在草稿目录里的隐藏临时目录生成（同一磁盘，最后一步改名即可），完成后再放到正式位置
    tmp_parent = tempfile.mkdtemp(prefix=".kewei-build-", dir=root)
    try:
        r = _build_into(cfg, caps, keywords, title, name, tmp_parent, motion, video, audio, bgm)
        fin = place.finalize(os.path.join(tmp_parent, name), root, name, duration_us=int(r["duration_s"] * 1e6),
                             replace=replace, do_register=register)
    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)
    r.update(fin)
    r.update({"draft_root": root, "found_by": det["found_by"]})
    if det["platform"] == "mac" and not draft_utils.mac_sandbox_ok(root):
        r["warning"] = "草稿目录不在剪映可访问的位置（~/Movies 等），剪映可能打不开素材"
    return r


def _build_into(cfg, caps, keywords, title, name, root, motion, video, audio, bgm) -> Dict:
    W, H, fps = cfg["width"], cfg["height"], cfg["fps"]
    total = caps[-1]["end"]

    script = draft.DraftFolder(root).create_draft(name, W, H, fps, allow_replace=False)
    draft_dir = os.path.join(root, name)

    # 素材轨（可选）：口播视频 / 配音 / BGM，先本地化到草稿目录
    if video:
        v = draft_utils.localize(os.path.abspath(video), draft_dir)
        mat = draft.VideoMaterial(v)
        dur = min(mat.duration / 1e6, total) if draft_utils.media_kind(v) == "video" else total
        script.append_track(draft.TrackSpec(TrackType.video, "主视频"))
        script.add_segment(draft.VideoSegment(mat, trange(0, f"{dur}s")), "主视频")
    if audio:
        a = draft_utils.localize(os.path.abspath(audio), draft_dir)
        mat = draft.AudioMaterial(a)
        script.append_track(draft.TrackSpec(TrackType.audio, "配音"))
        script.add_segment(draft.AudioSegment(mat, trange(0, f"{min(mat.duration / 1e6, total)}s"),
                                              volume=cfg.get("audio_volume", 0.8)), "配音")
    if bgm:
        b = draft_utils.localize(os.path.abspath(bgm), draft_dir)
        mat = draft.AudioMaterial(b)
        script.append_track(draft.TrackSpec(TrackType.audio, "BGM"))
        script.add_segment(draft.AudioSegment(mat, trange(0, f"{min(mat.duration / 1e6, total)}s"),
                                              volume=cfg.get("background_music_volume", 0.3)), "BGM")

    # 字幕轨
    cs = cfg["caption_style"]
    mname = motion if motion is not None else cfg.get("default_motion")
    mot = list_motions().get(mname) if mname and mname != "none" else None
    if mname and mname != "none" and not mot:
        raise KeyError(f"未知动效：{mname}")
    nseg = max(1, len(mot["segments"])) if mot and mot["multi_segment"] else 1
    tracks = []
    for j in range(nseg):
        tn = "内容字幕" if j == 0 else f"内容字幕{j + 1}"
        script.append_track(draft.TrackSpec(TrackType.text, tn))
        tracks.append(tn)

    seg_count = 0
    for c in caps:
        pieces = subtitles.split_caption(c, nseg, keywords) if nseg > 1 else [c]
        for j, p in enumerate(pieces):
            ms = mot["segments"][min(j, len(mot["segments"]) - 1)] if mot else None
            color = None
            if ms and ms.get("highlight"):
                color = cs["highlight_style"]["color"]
            elif ms and nseg > 1 and ms.get("color"):
                color = _hex_rgb(ms["color"])
            st, font, shadow, bg = _parts(cs, color)
            ox, oy = ms["position_offset"] if (ms and nseg > 1) else (0, 0)
            sc = ms["scale"] if (ms and nseg > 1) else 1.0
            clip = draft.ClipSettings(transform_x=ox / (W / 2), transform_y=cs["transform_y"] + oy / (H / 2),
                                      scale_x=sc, scale_y=sc)
            seg = HighlightTextSegment(p["text"], trange(f'{p["start"]}s', f'{max(p["end"] - p["start"], 0.1):.3f}s'),
                                       font=font, style=st, shadow=shadow, background=bg if j == 0 else None,
                                       clip_settings=clip, highlights=_highlights(p["text"], keywords, cs["highlight_style"]))
            anim = _intro(ms.get("intro_animation")) if ms else None
            if anim:
                seg.add_animation(anim, min(0.5, (p["end"] - p["start"]) / 2))
            _add_text(script, seg, tracks[j])
            seg_count += 1

    if title:
        ts = cfg["title_style"]
        script.append_track(draft.TrackSpec(TrackType.text, "标题"))
        st2, font2, shadow2, bg2 = _parts(ts)
        _add_text(script, HighlightTextSegment(title, trange("0s", f"{total}s"), font=font2, style=st2, shadow=shadow2,
                                                background=bg2, clip_settings=draft.ClipSettings(transform_y=ts["transform_y"]),
                                                highlights=_highlights(title, keywords, ts["highlight_style"])), "标题")

    script.save()
    paths.mirror_platform_json(draft_dir)
    draft_utils.generate_draft_cover(draft_dir, media=video, w=W, h=H, title=title)
    return {"template": cfg["id"], "motion": mname or "none", "captions": len(caps),
            "text_segments": seg_count, "duration_s": round(total, 3)}
