# SPDX-License-Identifier: Apache-2.0
"""把临时目录里生成好的草稿放进剪映草稿目录，并（可选）登记到 root_meta_info.json。

- 不覆盖已有草稿；--replace 时旧草稿移到 <草稿目录>/.kewei-replaced/ 备份，不直接删除。
- 草稿 JSON 里引用的素材绝对路径会从临时目录改写到最终目录。
- root_meta_info.json：剪映/CapCut 首页草稿列表的索引（Mac 与新版 CapCut 依赖它）。
  只在文件已存在、且剪映/CapCut 没有在运行时登记；登记前备份为 root_meta_info.json.kewei-<时间>.bak，
  并按已有条目的字段结构克隆新条目（兼容不同版本）。
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from typing import Dict, Optional

INDEX = "root_meta_info.json"


def validate_name(name: str) -> str:
    bad = set('<>:"/\\|?*') | {"\0"}
    if not name or name in (".", "..") or name.startswith(".") or any(ch in bad for ch in name):
        raise ValueError(f"草稿名不合法：{name!r}（不能含 / \\ : * ? \" < > | ，不能以 . 开头）")
    return name


def app_running() -> Optional[bool]:
    """剪映/CapCut 是否在运行。无法判断时返回 None。"""
    try:
        if sys.platform == "win32":
            out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10).stdout.lower()
            return "jianyingpro.exe" in out or "capcut.exe" in out
        if sys.platform == "darwin":
            r = subprocess.run(["pgrep", "-if", "JianyingPro|CapCut|VideoFusion"], capture_output=True, text=True, timeout=10)
            return bool(r.stdout.strip())
    except Exception:
        return None
    return None


def _rewrite_paths(draft_dir: str, old: str, new: str) -> None:
    if old == new:
        return
    pairs = {old: new, old.replace("\\", "/"): new.replace("\\", "/"),
             json.dumps(old)[1:-1]: json.dumps(new)[1:-1]}
    for fn in ("draft_content.json", "draft_info.json", "draft_meta_info.json"):
        p = os.path.join(draft_dir, fn)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            s = f.read()
        for a, b in pairs.items():
            s = s.replace(a, b)
        with open(p, "w", encoding="utf-8") as f:
            f.write(s)


def _fill_meta(draft_dir: str, root: str, name: str, duration_us: int) -> Dict:
    p = os.path.join(draft_dir, "draft_meta_info.json")
    with open(p, encoding="utf-8") as f:
        m = json.load(f)
    now = int(time.time() * 1e6)
    m.update({
        "draft_id": str(uuid.uuid4()).upper(),  # pyJianYingDraft 模板里的 draft_id 是固定值，每个草稿必须唯一
        "draft_name": name,
        "draft_fold_path": draft_dir.replace("\\", "/"),
        "draft_root_path": root.replace("\\", "/") if sys.platform != "win32" else root,
        "tm_draft_create": now, "tm_draft_modified": now, "tm_duration": duration_us,
    })
    if os.path.exists(os.path.join(draft_dir, "draft_cover.jpg")):
        m["draft_cover"] = "draft_cover.jpg"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False)
    return m


def register(root: str, draft_dir: str, meta: Dict, *, force: bool = False) -> Dict:
    """把草稿登记进 root_meta_info.json。返回 {registered, reason, backup}。"""
    idx = os.path.join(root, INDEX)
    if not os.path.exists(idx):
        return {"registered": False, "reason": "草稿目录里没有 root_meta_info.json（剪映按文件夹扫描，无需登记）"}
    if not force and app_running():
        return {"registered": False, "reason": "剪映/CapCut 正在运行，退出时会覆盖索引；请完全退出后运行 kewei-jianying register"}
    with open(idx, encoding="utf-8") as f:
        data = json.load(f)
    store = data.get("all_draft_store")
    if not isinstance(store, list):
        return {"registered": False, "reason": "root_meta_info.json 结构不认识，未修改"}
    bak = f"{idx}.kewei-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(idx, bak)
    fold = draft_dir.replace("\\", "/") if sys.platform != "win32" else draft_dir
    json_name = "draft_info.json" if sys.platform == "darwin" else "draft_content.json"
    base = copy.deepcopy(next((e for e in store if isinstance(e, dict)), {}))
    base.update({
        "draft_cover": os.path.join(fold, "draft_cover.jpg"),
        "draft_fold_path": fold,
        "draft_id": meta["draft_id"],
        "draft_is_invisible": False,
        "draft_json_file": os.path.join(fold, json_name),
        "draft_name": meta["draft_name"],
        "draft_root_path": data.get("root_path") or root,
        "tm_draft_create": meta["tm_draft_create"],
        "tm_draft_modified": meta["tm_draft_modified"],
        "tm_draft_removed": 0,
        "tm_duration": meta["tm_duration"],
    })
    for k in ("draft_cloud_last_action_download", "cloud_draft_sync", "cloud_draft_cover"):
        if k in base:
            base[k] = False
    data["all_draft_store"] = [base] + [e for e in store if not (isinstance(e, dict) and (
        e.get("draft_fold_path") == fold or e.get("draft_id") == meta["draft_id"]))]
    if isinstance(data.get("draft_ids"), int):
        data["draft_ids"] += 1
    tmp = idx + ".kewei-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, idx)
    return {"registered": True, "reason": "已登记到 root_meta_info.json", "backup": bak}


def finalize(tmp_dir: str, root: str, name: str, *, duration_us: int, replace: bool = False,
             do_register: bool = True) -> Dict:
    final = os.path.join(root, name)
    _rewrite_paths(tmp_dir, os.path.abspath(tmp_dir), os.path.abspath(final))
    replaced = None
    if os.path.exists(final):
        if not replace:
            raise FileExistsError(f"草稿「{name}」已存在：{final}（换个 --name，或加 --replace 覆盖，旧草稿会备份）")
        bdir = os.path.join(root, ".kewei-replaced")
        os.makedirs(bdir, exist_ok=True)
        replaced = os.path.join(bdir, f"{name}-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.move(final, replaced)
    shutil.move(tmp_dir, final)
    meta = _fill_meta(final, root, name, duration_us)
    reg = register(root, final, meta) if do_register else {"registered": False, "reason": "已用 --no-register 跳过"}
    return {"draft_dir": final, "draft_id": meta["draft_id"], "replaced_backup": replaced, **{f"index_{k}": v for k, v in reg.items()}}
