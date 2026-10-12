"""模拟 Mac / Windows 目录布局（假 HOME），测试草稿目录探测、放置与草稿索引登记。
运行：python -m unittest tests/test_detect_place.py"""
import json, os, plistlib, shutil, subprocess, sys, tempfile, time, unittest
from kewei_jianying import paths, place

J = os.path.join


def mkdraft(root, name, age=0):
    d = J(root, name); os.makedirs(d, exist_ok=True)
    p = J(d, "draft_meta_info.json"); open(p, "w").write("{}")
    t = time.time() - age; os.utime(p, (t, t))
    return d


class Detect(unittest.TestCase):
    def setUp(self):
        self.h = tempfile.mkdtemp(); self.env = {}

    def tearDown(self):
        shutil.rmtree(self.h, ignore_errors=True)

    def d(self, plat, explicit=None):
        return paths.detect(explicit, home=self.h, env=self.env, platform=plat)

    # 1. 显式
    def test_explicit_and_env(self):
        self.env[paths.ENV_VAR] = J(self.h, "envroot")
        self.assertEqual(self.d("mac")["path"], J(self.h, "envroot"))
        self.assertEqual(self.d("mac", "/x/y")["found_by"], "--draft-root")

    # 3. Mac 默认
    def test_mac_default(self):
        root = J(self.h, "Movies/JianyingPro/User Data/Projects/com.lveditor.draft"); mkdraft(root, "a")
        r = self.d("mac"); self.assertEqual(r["path"], root); self.assertIn("剪映默认目录", r["found_by"])

    def test_mac_empty_default_fallback(self):
        root = J(self.h, "Movies/JianyingPro/User Data/Projects/com.lveditor.draft"); os.makedirs(root)
        r = self.d("mac"); self.assertEqual(r["path"], root); self.assertIn("目录为空", r["found_by"])

    # 2. Mac 自定义：globalSetting
    def test_mac_global_setting_custom(self):
        custom = J(self.h, "Movies/我的草稿"); mkdraft(custom, "x")
        cfg = J(self.h, "Movies/JianyingPro/User Data/Config"); os.makedirs(cfg)
        open(J(cfg, "globalSetting"), "w", encoding="utf-8").write(f"[General]\ncacheDate=30\ncurrentCustomDraftPath={custom}\n")
        mkdraft(J(self.h, "Movies/JianyingPro/User Data/Projects/com.lveditor.draft"), "old", age=9999)
        r = self.d("mac"); self.assertEqual(r["path"], custom); self.assertIn("globalSetting", r["found_by"])

    # 2. Mac 自定义：沙盒 plist
    def test_mac_plist_custom(self):
        custom = J(self.h, "Movies/plist草稿"); mkdraft(custom, "x")
        pd = J(self.h, "Library/Containers/com.lemon.lvpro/Data/Library/Preferences"); os.makedirs(pd)
        plistlib.dump({"GlobalSettings.History.currentCustomDraftPath": custom}, open(J(pd, "com.bytedance.JianyingPro.plist"), "wb"))
        self.assertEqual(self.d("mac")["path"], custom)

    # CapCut Mac
    def test_mac_capcut(self):
        root = J(self.h, "Movies/CapCut/User Data/Projects/com.lveditor.draft"); mkdraft(root, "c")
        r = self.d("mac"); self.assertEqual(r["path"], root); self.assertIn("CapCut", r["found_by"])

    # 2. Windows 自定义（Windows 风格双反斜杠转义）
    def test_win_global_setting_custom(self):
        self.env["LOCALAPPDATA"] = J(self.h, "AppData/Local")
        custom = J(self.h, "D/jianying/JianyingPro Drafts"); mkdraft(custom, "x")
        cfg = J(self.h, "AppData/Local/JianyingPro/User Data/Config"); os.makedirs(cfg)
        open(J(cfg, "globalSetting"), "w").write("[General]\ncurrentCustomDraftPath=" + custom.replace("/", "\\\\") .replace("\\\\", "/") + "\n")
        self.assertEqual(self.d("win")["path"], custom)

    def test_unescape(self):
        self.assertEqual(paths._unescape_ini('"D:\\\\jianying\\\\JianyingPro Drafts"'), "D:\\jianying\\JianyingPro Drafts")
        self.assertEqual(paths._unescape_ini("C:/x/\\x8349\\x7a3f"), "C:/x/草稿")

    # 3. Windows 默认
    def test_win_default(self):
        self.env["LOCALAPPDATA"] = J(self.h, "AppData/Local")
        root = J(self.h, "AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft"); mkdraft(root, "a")
        self.assertEqual(self.d("win")["path"], root)

    # 4. 扫描 D:/E: 取最近更新
    def test_win_scan_drives_most_recent(self):
        self.env["LOCALAPPDATA"] = J(self.h, "AppData/Local")
        D, E = J(self.h, "D"), J(self.h, "E"); self.env["KEWEI_TEST_DRIVES"] = os.pathsep.join([D, E])
        mkdraft(J(D, "JianyingPro Drafts"), "old", age=86400)
        mkdraft(J(E, "视频剪映草稿"), "new", age=10)
        os.makedirs(J(self.h, "AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft"))  # 空默认目录不应胜出
        r = self.d("win"); self.assertEqual(r["path"], J(E, "视频剪映草稿")); self.assertIn("扫描", r["found_by"])

    def test_nothing(self):
        self.assertIsNone(self.d("win")["path"])


class Place(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _tmpdraft(self, name):
        tp = tempfile.mkdtemp(prefix=".kewei-build-", dir=self.root); d = J(tp, name); os.makedirs(J(d, "materials"))
        open(J(d, "materials/a.mp4"), "w").write("x")
        c = json.dumps({"materials": {"videos": [{"path": J(d, "materials/a.mp4")}]}})
        for f in ("draft_content.json", "draft_info.json"): open(J(d, f), "w").write(c)
        open(J(d, "draft_meta_info.json"), "w").write(json.dumps({"draft_id": "BC69C7CD-7C5E-4185-B284-AF3E1047A664"}))
        return d

    def test_place_rewrite_register_replace(self):
        idx = J(self.root, "root_meta_info.json")
        existing = {"draft_name": "旧", "draft_fold_path": "/x/旧", "draft_id": "OLD", "some_future_field": 7, "cloud_draft_sync": True}
        json.dump({"all_draft_store": [existing], "draft_ids": 1, "root_path": self.root}, open(idx, "w"))
        r = place.finalize(self._tmpdraft("新草稿"), self.root, "新草稿", duration_us=5_000_000)
        final = J(self.root, "新草稿")
        self.assertEqual(r["draft_dir"], final)
        c = json.load(open(J(final, "draft_content.json")))
        self.assertEqual(c["materials"]["videos"][0]["path"], J(final, "materials/a.mp4"))  # 路径已改写
        m = json.load(open(J(final, "draft_meta_info.json")))
        self.assertNotEqual(m["draft_id"], "BC69C7CD-7C5E-4185-B284-AF3E1047A664")
        self.assertEqual((m["draft_name"], m["tm_duration"]), ("新草稿", 5_000_000))
        self.assertTrue(r["index_registered"]); self.assertTrue(os.path.exists(r["index_backup"]))
        store = json.load(open(idx))["all_draft_store"]
        self.assertEqual([e["draft_name"] for e in store], ["新草稿", "旧"])
        self.assertEqual(store[0]["some_future_field"], 7)  # 克隆已有条目结构
        self.assertFalse(store[0]["cloud_draft_sync"]); self.assertEqual(store[1], existing)  # 旧条目原样保留
        # 不覆盖
        with self.assertRaises(FileExistsError):
            place.finalize(self._tmpdraft("新草稿"), self.root, "新草稿", duration_us=1)
        # --replace：旧的备份，索引不重复
        r2 = place.finalize(self._tmpdraft("新草稿"), self.root, "新草稿", duration_us=1, replace=True)
        self.assertTrue(os.path.isdir(r2["replaced_backup"]))
        store = json.load(open(idx))["all_draft_store"]
        self.assertEqual([e["draft_name"] for e in store], ["新草稿", "旧"])

    def test_no_index_no_write(self):
        r = place.finalize(self._tmpdraft("a"), self.root, "a", duration_us=1)
        self.assertFalse(r["index_registered"]); self.assertFalse(os.path.exists(J(self.root, "root_meta_info.json")))

    def test_bad_names(self):
        for n in ("../x", "a/b", ".hidden", "a:b", ""):
            with self.assertRaises(ValueError):
                place.validate_name(n)


class CliFakeHome(unittest.TestCase):
    """完整 CLI：假 HOME + 模拟平台，不传 --draft-root，build 自动落到探测到的目录。"""
    def test_cli_mac_and_win(self):
        exe = shutil.which("kewei-jianying") or J(os.path.dirname(sys.executable), "kewei-jianying")
        srt = J(os.path.dirname(__file__), "..", "examples", "sample.srt")
        for plat in ("mac", "win"):
            h = tempfile.mkdtemp()
            env = {k: v for k, v in os.environ.items() if k != paths.ENV_VAR}
            env.update(HOME=h, KEWEI_TEST_PLATFORM=plat, LOCALAPPDATA=J(h, "AppData/Local"), KEWEI_TEST_DRIVES="")
            custom = J(h, "Movies/自定义草稿") if plat == "mac" else J(h, "D/剪映草稿")
            mkdraft(custom, "已有草稿")
            json.dump({"all_draft_store": [], "draft_ids": 0, "root_path": custom}, open(J(custom, "root_meta_info.json"), "w"))
            ud = J(h, "Movies/JianyingPro/User Data") if plat == "mac" else J(h, "AppData/Local/JianyingPro/User Data")
            os.makedirs(J(ud, "Config")); os.makedirs(J(ud, "Projects/com.lveditor.draft"))
            open(J(ud, "Config/globalSetting"), "w").write(f"[General]\ncurrentCustomDraftPath={custom}\n")
            w = json.loads(subprocess.run([exe, "where", "--json"], env=env, capture_output=True, text=True).stdout)
            self.assertEqual(w["path"], custom, plat)
            out = subprocess.run([exe, "build", "-t", "zhishi-koubo", "--srt", srt, "-n", "自动放置", "--json"],
                                 env=env, capture_output=True, text=True)
            r = json.loads(out.stdout)
            self.assertTrue(r["ok"], out.stderr); self.assertEqual(r["draft_dir"], J(custom, "自动放置"))
            self.assertTrue(r["index_registered"])
            self.assertFalse([n for n in os.listdir(custom) if n.startswith(".kewei-build-")])  # 临时目录已清理
            again = subprocess.run([exe, "build", "-t", "zhishi-koubo", "--srt", srt, "-n", "自动放置", "--json"],
                                   env=env, capture_output=True, text=True)
            self.assertEqual(again.returncode, 2)
            shutil.rmtree(h)


if __name__ == "__main__":
    unittest.main()
