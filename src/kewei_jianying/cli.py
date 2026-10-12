# SPDX-License-Identifier: Apache-2.0
"""kewei-jianying 命令行：--version / doctor / list / build"""
import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path

from . import __version__

CTA = "需要批量出片、选题脚本或团队定制模板？→ 可为AI keweiai.cn"


def _kws(v):
    if not v:
        return []
    p = Path(v)
    if p.is_file():
        return [str(x) for x in json.loads(p.read_text(encoding="utf-8"))]
    return [k.strip() for k in v.replace("，", ",").split(",") if k.strip()]


def cmd_doctor(a) -> int:
    from . import paths
    ok = True
    rows = [("kewei-jianying", __version__, True)]
    py_ok = sys.version_info >= (3, 9)
    rows.append(("Python", platform.python_version(), py_ok)); ok &= py_ok
    try:
        import importlib.metadata as md
        v = md.version("pyJianYingDraft"); rows.append(("pyJianYingDraft", v, v.startswith("0.3")))
    except Exception:
        rows.append(("pyJianYingDraft", "未安装", False)); ok = False
    rows.append(("ffmpeg（可选，视频封面截帧）", shutil.which("ffmpeg") or "未找到", True))
    det = paths.detect(a.draft_root)
    root = det["path"]
    rows.append(("剪映草稿目录", f"{root}（{det['found_by']}）" if root else "未找到 → 运行 kewei-jianying where 看候选，或用 --draft-root", bool(root)))
    if a.json:
        print(json.dumps({"ok": bool(ok and root), "checks": [{"name": n, "value": v, "ok": o} for n, v, o in rows],
                          "draft_root": root, "found_by": det["found_by"], "candidates": det["candidates"]}, ensure_ascii=False))
    else:
        for n, v, o in rows:
            print(f"{'✅' if o else '❌'} {n}: {v}")
        if not root:
            _print_candidates(det)
    return 0 if ok and root else 1


def _print_candidates(det):
    print("候选目录：")
    for c in det["candidates"]:
        st = (f"存在，{c.get('drafts', 0)} 个草稿" + ("，有草稿索引" if c.get("has_index") else "")) if c["exists"] else "不存在"
        print(f"  {'→' if c['path'] == det['path'] else ' '} {c['path']}  [{c['source']}] {st}")


def cmd_where(a) -> int:
    from . import paths
    det = paths.detect(a.draft_root)
    if a.json:
        print(json.dumps(det, ensure_ascii=False, indent=1))
    else:
        print(f"{'✅' if det['path'] else '❌'} 剪映草稿目录：{det['path'] or '未找到'}")
        print(f"   来源：{det['found_by']}（{det['platform']}）")
        _print_candidates(det)
    return 0 if det["path"] else 1


def cmd_register(a) -> int:
    from . import paths, place
    root = paths.detect(a.draft_root)["path"]
    d = os.path.join(root or "", a.name)
    mp = os.path.join(d, "draft_meta_info.json")
    if not root or not os.path.exists(mp):
        print(f"❌ 找不到草稿：{d}", file=sys.stderr); return 2
    meta = json.load(open(mp, encoding="utf-8"))
    r = place.register(root, d, meta, force=a.force)
    print(json.dumps(r, ensure_ascii=False) if a.json else f"{'✅' if r['registered'] else 'ℹ️'} {r['reason']}")
    return 0


def cmd_list(a) -> int:
    from .builder import list_motions, list_templates
    ts = list_templates()
    if a.json:
        print(json.dumps({"templates": [{k: t.get(k) for k in ("id", "name", "description", "tags", "default_motion")} for t in ts],
                          "motions": {k: v["name"] for k, v in list_motions().items()}}, ensure_ascii=False, indent=1))
        return 0
    print("字幕模板：")
    for t in ts:
        print(f"  {t['id']:<18}{t['name']}  — {t.get('description', '')}（默认动效 {t.get('default_motion')}）")
    print("动效（--motion，none 表示不加）：")
    print("  " + "  ".join(f"{k}({v['name']})" for k, v in list_motions().items()))
    return 0


def cmd_build(a) -> int:
    from .builder import build
    text = Path(a.text_file).read_text(encoding="utf-8") if a.text_file else a.text
    r = build(a.template, srt=a.srt, text=text, keywords=_kws(a.keywords), title=a.title or "", name=a.name,
              draft_root=a.draft_root, motion=a.motion, video=a.video, audio=a.audio, bgm=a.bgm, replace=a.replace,
              register=not a.no_register)
    if a.json:
        print(json.dumps({"ok": True, **r}, ensure_ascii=False))
    else:
        print(f"✅ 已生成剪映草稿「{a.name}」")
        print(f"   位置：{r['draft_dir']}")
        print(f"   草稿目录来源：{r['found_by']}")
        print(f"   模板 {r['template']} · 动效 {r['motion']} · {r['captions']} 条字幕 · {r['duration_s']}s")
        if r.get("replaced_backup"):
            print(f"   旧草稿已备份到：{r['replaced_backup']}")
        print(f"   草稿列表索引：{r.get('index_reason')}")
        if r.get("warning"):
            print(f"⚠️ {r['warning']}")
        print("   打开剪映专业版 → 首页草稿列表找到同名草稿。没看到：完全退出剪映再打开" +
              ("，如提示正在运行未登记，退出剪映后运行 kewei-jianying register " + a.name if not r.get("index_registered") and "运行" in str(r.get("index_reason")) else "") + "。")
        print(CTA)
    return 0


def cmd_install_skill(a) -> int:
    from importlib import resources
    targets = {"workbuddy": "~/.workbuddy/skills", "codebuddy": "~/.codebuddy/skills",
               "claude": "~/.claude/skills", "codex": "~/.codex/skills"}
    dest_root = Path(os.path.expanduser(a.dir or targets[a.agent]))
    dest = dest_root / "kewei-jianying"
    src = resources.files(__package__) / "skill"
    for rel in ("SKILL.md", "references/template-schema.md"):
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text((src / rel).read_text(encoding="utf-8"), encoding="utf-8")
    print(f"✅ 技能已安装到 {dest}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kewei-jianying", description="可为AI 开源剪映字幕模板：一句话生成可编辑的剪映草稿")
    ap.add_argument("--version", action="version", version=f"kewei-jianying {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="检查环境与剪映草稿目录")
    d.add_argument("--draft-root"); d.add_argument("--json", action="store_true"); d.set_defaults(fn=cmd_doctor)

    w = sub.add_parser("where", help="显示自动探测到的剪映草稿目录、来源和全部候选")
    w.add_argument("--draft-root"); w.add_argument("--json", action="store_true"); w.set_defaults(fn=cmd_where)

    g = sub.add_parser("register", help="把已生成的草稿登记到剪映草稿列表索引（需先退出剪映）")
    g.add_argument("name"); g.add_argument("--draft-root"); g.add_argument("--force", action="store_true",
                   help="不检查剪映是否在运行"); g.add_argument("--json", action="store_true"); g.set_defaults(fn=cmd_register)

    l = sub.add_parser("list", help="列出模板与动效")
    l.add_argument("--json", action="store_true"); l.set_defaults(fn=cmd_list)

    s = sub.add_parser("install-skill", help="把 SKILL.md 安装到 Agent 的技能目录（默认 WorkBuddy）")
    s.add_argument("--agent", choices=["workbuddy", "codebuddy", "claude", "codex"], default="workbuddy")
    s.add_argument("--dir", help="自定义技能根目录")
    s.set_defaults(fn=cmd_install_skill)

    b = sub.add_parser("build", help="生成剪映草稿")
    b.add_argument("--template", "-t", required=True, help="模板 id、名称或 template.json 路径")
    src = b.add_mutually_exclusive_group(required=True)
    src.add_argument("--srt", help="SRT 字幕文件")
    src.add_argument("--text", help="口播稿文本（按标点切句并估算时长）")
    src.add_argument("--text-file", help="口播稿文本文件")
    b.add_argument("--keywords", "-k", help="关键词：逗号分隔或 JSON 数组文件")
    b.add_argument("--title", help="顶部标题")
    b.add_argument("--name", "-n", default="kewei-draft", help="草稿名称")
    b.add_argument("--motion", "-m", help="动效 id；none 不加；默认用模板的 default_motion")
    b.add_argument("--video", help="口播视频或背景图（可选）")
    b.add_argument("--audio", help="配音音频（可选）")
    b.add_argument("--bgm", help="背景音乐（可选）")
    b.add_argument("--draft-root", help="剪映草稿目录；默认自动探测或读环境变量 KEWEI_JIANYING_DRAFT_ROOT")
    b.add_argument("--replace", action="store_true", help="同名草稿存在时替换（旧草稿备份到 .kewei-replaced/）")
    b.add_argument("--no-register", action="store_true", help="不写剪映草稿列表索引 root_meta_info.json")
    b.add_argument("--json", action="store_true", help="输出 JSON 结果（便于 Agent 解析）")
    b.set_defaults(fn=cmd_build)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (KeyError, ValueError, FileNotFoundError, FileExistsError) as e:
        msg = e.args[0] if e.args else str(e)
        print(json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False) if getattr(a, "json", False) else f"❌ {msg}",
              file=sys.stderr)
        return 2
