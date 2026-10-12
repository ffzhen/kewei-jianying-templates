"""校验生成的剪映草稿文件夹结构与引用完整性。用法: python validate_draft.py <草稿目录>..."""
import json, os, sys

def check(d):
    errs = []
    c = json.load(open(os.path.join(d, "draft_content.json"), encoding="utf-8"))
    if open(os.path.join(d, "draft_content.json"), "rb").read() != open(os.path.join(d, "draft_info.json"), "rb").read():
        errs.append("draft_info.json 与 draft_content.json 不一致")
    meta = json.load(open(os.path.join(d, "draft_meta_info.json"), encoding="utf-8"))
    if meta.get("draft_cover") != "draft_cover.jpg" or not os.path.getsize(os.path.join(d, "draft_cover.jpg")):
        errs.append("封面缺失")
    if meta.get("draft_id") == "BC69C7CD-7C5E-4185-B284-AF3E1047A664" or meta.get("draft_name") != os.path.basename(d.rstrip("/")):
        errs.append("draft_meta_info 未填写唯一 draft_id / draft_name")
    if (c["canvas_config"]["width"], c["canvas_config"]["height"]) != (1080, 1920): errs.append("画布不是 1080x1920")
    ids = {m["id"] for lst in c["materials"].values() if isinstance(lst, list) for m in lst if isinstance(m, dict) and "id" in m}
    nseg = 0
    for t in c["tracks"]:
        last = -1
        for s in sorted(t["segments"], key=lambda s: s["target_timerange"]["start"]):
            nseg += 1
            if s["material_id"] not in ids: errs.append(f"{t['name']}: material_id 不存在")
            for r in s.get("extra_material_refs", []):
                if r not in ids: errs.append(f"{t['name']}: extra ref 不存在 {r}")
            st, du = s["target_timerange"]["start"], s["target_timerange"]["duration"]
            if du <= 0 or st < last: errs.append(f"{t['name']}: 时间重叠/非法")
            last = st + du
    for m in c["materials"]["texts"]:
        ct = json.loads(m["content"]); L = len(ct["text"]); cur = 0
        for s in ct["styles"]:
            a, b = s["range"]
            if a != cur or b > L: errs.append(f"文本样式区间错误: {ct['text']}"); break
            cur = b
        if cur != L: errs.append(f"样式未覆盖全文: {ct['text']}")
    if c["duration"] <= 0: errs.append("时长为 0")
    for m in c["materials"]["videos"] + c["materials"]["audios"]:
        if not os.path.exists(m["path"]): errs.append(f"素材路径不存在 {m['path']}")
    return errs, len(c["tracks"]), nseg, c["duration"] / 1e6

bad = 0
for d in sys.argv[1:]:
    e, nt, ns, du = check(d)
    print(("OK  " if not e else "FAIL"), os.path.basename(d), f"tracks={nt} segments={ns} dur={du:.2f}s", *e[:5])
    bad += bool(e)
sys.exit(1 if bad else 0)
