# SPDX-License-Identifier: Apache-2.0
"""草稿封面与素材本地化。

移植自可为AI Tigenix 平台 python-video-service/lib/jianying_utils.py（generate_draft_cover）
与其 pyJianYingDraft 副本中的 ScriptFile._copy_materials_to_draft_dir，去掉了服务端依赖。
"""
import json
import os
import shutil
import subprocess
import sys
import uuid
from typing import Optional

DRAFT_COVER_FILENAME = "draft_cover.jpg"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def media_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return "image" if ext in IMAGE_EXT else "video" if ext in VIDEO_EXT else "audio"


def mac_sandbox_ok(path: str) -> bool:
    return not _needs_localize_mac(path)


def _needs_localize_mac(path: str) -> bool:
    home = os.path.expanduser("~")
    ok = [os.path.join(home, d) for d in ("Movies", "Documents", "Downloads", "Desktop", "Music", "Pictures")]
    ok.append(os.path.join(home, "Library", "Containers", "com.lemon.lvpro"))
    ap = os.path.abspath(path)
    return not any(ap == p or ap.startswith(p + os.sep) for p in ok)


def _needs_localize(path: str) -> bool:
    if sys.platform != "darwin":
        return True  # Windows/其他：总是放进草稿目录，草稿与素材解耦
    home = os.path.expanduser("~")
    ok = [os.path.join(home, d) for d in ("Movies", "Documents", "Downloads", "Desktop", "Music", "Pictures")]
    ok.append(os.path.join(home, "Library", "Containers", "com.lemon.lvpro"))
    ap = os.path.abspath(path)
    return not any(ap.startswith(p + os.sep) for p in ok)


def localize(path: str, draft_dir: str) -> str:
    """把素材硬链接/复制到 <草稿>/materials/，Mac 剪映沙盒外的文件必须这样做才能打开。"""
    if not path or not os.path.exists(path) or not _needs_localize(path):
        return path
    ap, ad = os.path.abspath(path), os.path.abspath(draft_dir)
    if ap.startswith(ad + os.sep):
        return path
    mdir = os.path.join(draft_dir, "materials")
    os.makedirs(mdir, exist_ok=True)
    base, ext = os.path.splitext(os.path.basename(path))
    dst = os.path.join(mdir, base + ext)
    if os.path.exists(dst):
        dst = os.path.join(mdir, f"{base}_{uuid.uuid4().hex[:8]}{ext}")
    try:
        os.link(path, dst)
    except OSError:
        shutil.copy2(path, dst)
    return dst


def _save_image_cover(src: str, cover: str, w: int, h: int) -> bool:
    try:
        from PIL import Image
        with Image.open(src) as im:
            im.convert("RGB").resize((w, h)).save(cover, "JPEG", quality=85)
        return os.path.getsize(cover) > 0
    except Exception:
        return False


def _video_frame_cover(src: str, cover: str, w: int, h: int) -> bool:
    ff = shutil.which("ffmpeg")
    if not ff:
        return False
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
    for t in ("0.5", "0"):
        try:
            r = subprocess.run([ff, "-y", "-ss", t, "-i", src, "-frames:v", "1", "-q:v", "2", "-vf", vf, cover],
                               capture_output=True, timeout=20)
            if r.returncode == 0 and os.path.exists(cover) and os.path.getsize(cover) > 1024:
                return True
        except Exception:
            pass
    return False


def _solid_cover(cover: str, w: int, h: int, text: str = "") -> bool:
    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (w, h), (18, 18, 22))
        if text:
            ImageDraw.Draw(im).rectangle([0, h * 0.42, w, h * 0.58], fill=(255, 191, 63))
        im.save(cover, "JPEG", quality=85)
        return True
    except Exception:
        return False


def generate_draft_cover(draft_dir: str, media: Optional[str] = None, w: int = 1080, h: int = 1920,
                         title: str = "") -> bool:
    """生成剪映草稿列表预览图 draft_cover.jpg，并写入 draft_meta_info.json。"""
    cover = os.path.join(draft_dir, DRAFT_COVER_FILENAME)
    ok = False
    if media and os.path.exists(media):
        k = media_kind(media)
        ok = _save_image_cover(media, cover, w, h) if k == "image" else _video_frame_cover(media, cover, w, h) if k == "video" else False
    ok = ok or _solid_cover(cover, w, h, title)
    meta = os.path.join(draft_dir, "draft_meta_info.json")
    if ok and os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            m = json.load(f)
        m["draft_cover"] = DRAFT_COVER_FILENAME
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False)
    return ok
