# SPDX-License-Identifier: Apache-2.0
"""剪映 / CapCut 草稿目录探测。来源与验证情况见 docs/draft-location.md。

探测顺序：
 1. --draft-root 参数 / 环境变量 KEWEI_JIANYING_DRAFT_ROOT
 2. 剪映/CapCut 自己的设置文件里的自定义「草稿位置」
    - <User Data>/Config/globalSetting（INI，键 currentCustomDraftPath）
    - macOS 沙盒 plist：~/Library/Containers/com.lemon.lvpro/Data/Library/Preferences/com.bytedance.JianyingPro.plist
      （键 GlobalSettings.History.currentCustomDraftPath）
 3. 各系统默认目录（存在且里面有草稿）
 4. 扫描常见自定义位置（含 D:/E: 盘的 JianyingPro Drafts），取最近有草稿更新的目录
 最后兜底：存在但为空的默认目录。
"""
import os
import plistlib
import re
import sys
from typing import Dict, List, Optional

ENV_VAR = "KEWEI_JIANYING_DRAFT_ROOT"
DRAFT_MARKERS = ("draft_meta_info.json", "draft_content.json", "draft_info.json")
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"


def _plat(platform: Optional[str]) -> str:
    p = platform or sys.platform
    return "mac" if p in ("darwin", "mac") else "win" if p in ("win32", "win") else "other"


def _unescape_ini(v: str) -> str:
    v = v.strip().strip('"').strip("'")
    v = re.sub(r"\\x([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), v)  # Qt 对非 ASCII 的 \xNNNN 转义（未实测）
    return v.replace("\\\\", "\\")


def read_global_setting(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("currentCustomDraftPath="):
                    v = _unescape_ini(line.split("=", 1)[1])
                    return os.path.expandvars(os.path.expanduser(v)) if v else None
    except OSError:
        pass
    return None


def read_mac_plist(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            v = plistlib.load(f).get("GlobalSettings.History.currentCustomDraftPath")
        return os.path.expanduser(v) if v else None
    except Exception:
        return None


def user_data_dirs(home: str, env: Dict[str, str], platform: str) -> List[tuple]:
    """(产品, User Data 目录)"""
    if platform == "mac":
        return [("剪映", os.path.join(home, "Movies", "JianyingPro", "User Data")),
                ("CapCut", os.path.join(home, "Movies", "CapCut", "User Data"))]
    if platform == "win":
        local = env.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return [("剪映", os.path.join(local, "JianyingPro", "User Data")),
                ("CapCut", os.path.join(local, "CapCut", "User Data"))]
    return []


def _drive_roots(env: Dict[str, str]) -> List[str]:
    if "KEWEI_TEST_DRIVES" in env:  # 测试用：模拟 D:/E: 盘
        return [d for d in env["KEWEI_TEST_DRIVES"].split(os.pathsep) if d]
    return [f"{c}:\\" for c in "CDEFG"]


def _scan_extra(home: str, env: Dict[str, str], platform: str) -> List[str]:
    out = []
    if platform == "mac":
        out += [os.path.join(home, "Movies", "JianyingPro Drafts"), os.path.join(home, "Documents", "JianyingPro Drafts")]
    elif platform == "win":
        out += [os.path.join(home, "Documents", "JianyingPro Drafts"), os.path.join(home, "JianyingPro Drafts")]
        for d in _drive_roots(env):
            out += [os.path.join(d, "JianyingPro Drafts"), os.path.join(d, "jianying", "JianyingPro Drafts"),
                    os.path.join(d, "JianyingPro", "JianyingPro Drafts"), os.path.join(d, "CapCut Drafts"),
                    os.path.join(d, "剪映草稿")]
            try:  # 盘符根目录下一层里名字含 Drafts / 草稿 / com.lveditor.draft 的目录
                for n in os.listdir(d):
                    if re.search(r"drafts|草稿|lveditor", n, re.I):
                        out.append(os.path.join(d, n))
            except OSError:
                pass
    return out


def draft_stats(path: str) -> Dict:
    n, latest = 0, 0.0
    try:
        for e in os.scandir(path):
            if e.is_dir() and not e.name.startswith("."):
                for m in DRAFT_MARKERS:
                    p = os.path.join(e.path, m)
                    if os.path.exists(p):
                        n += 1
                        latest = max(latest, os.path.getmtime(p))
                        break
    except OSError:
        pass
    has_index = os.path.exists(os.path.join(path, "root_meta_info.json"))
    return {"drafts": n, "latest": latest, "has_index": has_index}


def detect(explicit: Optional[str] = None, *, home: Optional[str] = None, env: Optional[Dict[str, str]] = None,
           platform: Optional[str] = None) -> Dict:
    home = home or os.path.expanduser("~")
    env = dict(os.environ) if env is None else env
    plat = _plat(platform or env.get("KEWEI_TEST_PLATFORM"))
    cands: List[Dict] = []

    def add(path, source):
        if path and not any(os.path.normcase(c["path"]) == os.path.normcase(path) for c in cands):
            c = {"path": path, "source": source, "exists": os.path.isdir(path)}
            if c["exists"]:
                c.update(draft_stats(path))
            cands.append(c)

    def result(c, how):
        return {"path": c["path"] if c else None, "found_by": how, "platform": plat, "candidates": cands}

    # 1. 显式指定
    if explicit:
        add(explicit, "--draft-root")
        return result(cands[-1], "--draft-root")
    if env.get(ENV_VAR):
        add(env[ENV_VAR], f"环境变量 {ENV_VAR}")
        return result(cands[-1], f"环境变量 {ENV_VAR}")

    # 2. 剪映/CapCut 设置文件里的自定义草稿位置
    uds = user_data_dirs(home, env, plat)
    for prod, ud in uds:
        gs = os.path.join(ud, "Config", "globalSetting")
        add(read_global_setting(gs), f"{prod}设置 {gs}")
    if plat == "mac":
        pl = os.path.join(home, "Library", "Containers", "com.lemon.lvpro", "Data", "Library", "Preferences",
                          "com.bytedance.JianyingPro.plist")
        add(read_mac_plist(pl), f"剪映设置 {pl}")
    configured = [c for c in cands if c["exists"]]
    if configured:
        best = max(configured, key=lambda c: (c.get("latest", 0), c.get("drafts", 0)))
        return result(best, best["source"])

    # 3. 默认目录（有草稿或有草稿索引的）
    n0 = len(cands)
    for prod, ud in uds:
        add(os.path.join(ud, "Projects", "com.lveditor.draft"), f"{prod}默认目录")
    defaults = cands[n0:]
    used = [c for c in defaults if c["exists"] and (c.get("drafts") or c.get("has_index"))]
    if used:
        best = max(used, key=lambda c: (c.get("latest", 0), c.get("drafts", 0)))
        return result(best, best["source"])

    # 4. 扫描常见自定义位置，取最近有草稿更新的
    for p in _scan_extra(home, env, plat):
        add(p, "扫描常见位置")
    scanned = [c for c in cands if c["exists"] and c.get("drafts")]
    if scanned:
        best = max(scanned, key=lambda c: (c.get("latest", 0), c.get("drafts", 0)))
        return result(best, best["source"] + "（含草稿最近更新）")

    # 兜底：存在但为空的默认目录（剪映装了还没建过草稿）
    empty = [c for c in defaults if c["exists"]]
    if empty:
        return result(empty[0], empty[0]["source"] + "（目录为空）")
    return result(None, "未找到")


def candidate_roots() -> List[str]:
    return [c["path"] for c in detect()["candidates"]]


def find_draft_root(explicit: Optional[str] = None) -> Optional[str]:
    return detect(explicit)["path"]


def mirror_platform_json(draft_dir: str) -> None:
    """pyJianYingDraft 0.3 只写 draft_content.json；Mac 版剪映读取 draft_info.json。两个都写。"""
    src = os.path.join(draft_dir, "draft_content.json")
    dst = os.path.join(draft_dir, "draft_info.json")
    if os.path.exists(src):
        with open(src, "rb") as f, open(dst, "wb") as g:
            g.write(f.read())
