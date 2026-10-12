# 剪映草稿目录探测与草稿列表登记：依据与验证状态

整理时间 2026-10-13。✅ = 有公开源码或文档佐证；⚠️ = 仅间接佐证或推断；❓ = 未证实，需要真机确认。

## 1. 自定义「草稿位置」存在哪里

| 平台 | 文件 / 键 | 状态 | 依据 |
|---|---|---|---|
| Windows 剪映 | `%LOCALAPPDATA%\JianyingPro\User Data\Config\globalSetting`，INI 行 `currentCustomDraftPath=` | ✅ | mackjosn/com.linker.jianying.sdk `paths.go`（读取该文件，`\\`→`\` 反转义）；DonghuaLuo/manju-xiaowo-plugin `backend/utils/arcreel_ipc_bridge.py::_detect_jianying_custom_draft_paths`（configparser 读 `[General] currentCustomDraftPath`） |
| macOS 剪映 | `~/Movies/JianyingPro/User Data/Config/globalSetting` 同一个键 | ⚠️ | com.linker.jianying.sdk 把 mac 的 User Data 定为 `~/Movies/JianyingPro/User Data`；未见 mac 剪映真实文件样本 |
| macOS 剪映（沙盒版） | `~/Library/Containers/com.lemon.lvpro/Data/Library/Preferences/com.bytedance.JianyingPro.plist`，键 `GlobalSettings.History.currentCustomDraftPath` | ✅ | inkyhu/resolve-jianying-bridge `installer/Install-mac.command::find_draft_root` |
| macOS CapCut | `~/Movies/CapCut/User Data/Config/globalSetting`，`currentCustomDraftPath=/Users/…/Movies/CapCut/User Data/Projects/com.lveditor.draft` | ✅ | ciobar22/dcbr-agency-test 仓库里的真实 `globalSetting` 文件；Tungcoi/AutoExportCapcut `MacOs/ui.py` |
| Windows CapCut | `%LOCALAPPDATA%\CapCut\User Data\Config\globalSetting` | ⚠️ | 按剪映同构推断（Tungcoi/AutoExportCapcut Windows 版同样读 globalSetting） |
| 非 ASCII 路径的 Qt `\xNNNN` 转义 | 已兼容解码 | ❓ | 推断（Qt INI 规则），未见真实样本 |

## 2. 默认草稿目录

| 平台 | 路径 | 状态 | 依据 |
|---|---|---|---|
| Windows 剪映 | `%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft` | ✅ | capcut-cli 文档（unpkg capcut-cli@0.23.0 quickstart）、PyPI jianying-tool 0.2.0（剪映 11.4.2 基线）、com.linker.jianying.sdk README、capcut-mate 配置示例 `DRAFT_SAVE_PATH`、luoluoluo22/jianying-editor-skill |
| macOS 剪映 | `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft` | ✅ | 同上 + 可为AI Tigenix 平台 `electron/mapi/file/index.ts` |
| macOS CapCut | `~/Movies/CapCut/User Data/Projects/com.lveditor.draft` | ✅ | resolve-jianying-bridge、dcbr-agency-test globalSetting |
| Windows CapCut | `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft` | ⚠️ | capcut-cli 称候选列表含 CapCut 路径；未逐字核对 |
| 常见自定义 | `D:\…\JianyingPro Drafts`、`~/Documents/JianyingPro Drafts` 等 | ⚠️ | pyJianYingDraft README（".../JianyingPro Drafts"）、CSDN 博文（`D:\doc\JianyingPro\JianyingPro Drafts`）、Tigenix 默认 `D:\jianying\JianyingPro Drafts`。仅作扫描候选 |

## 3. 新草稿会不会自动出现在剪映首页

- `root_meta_info.json`（草稿目录根下，`all_draft_store` 数组）是首页草稿列表索引：
  - ✅ CapCut：renezander030/capcut-cli PR #33「CapCut's GUI does not scan the Projects folder… builds its project list from root_meta_info.json」，不登记重启后也不显示。
  - ✅ 韩文博客 aivideolab.tistory.com/1：必须插入 `all_draft_store`；**CapCut 运行时改它，退出时会被整份覆盖**，所以必须先退出。
  - ✅ macOS 剪映：yehyakin/hermes-skills `jianying-editor-skill/SKILL.md`、Vincentwei1021/video-shotcraft `jianying-export/mac_draft.py`（先确认剪映未运行，备份后原子写入，条目插在最前）。
  - ⚠️ Windows 剪映：pyJianYingDraft README 只说「可能需要进入再退出某个草稿或重启剪映以刷新」；capcut-mate 用 robocopy 触发目录变更通知后无需重启即可识别 → Windows 版看起来会扫描文件夹。新版是否也依赖索引 ❓。
- 本工具的做法：索引文件存在且剪映/CapCut 未运行时才登记（克隆已有条目结构，先备份 `root_meta_info.json.kewei-<时间>.bak`，原子替换）；剪映运行中则跳过，提示退出后运行 `kewei-jianying register <草稿名>`；索引不存在时不创建。
- ✅ pyJianYingDraft 0.3 自带的 `draft_meta_info.json` 模板里 `draft_id` 是固定值，多个草稿会重复，本工具为每个草稿生成新的 UUID 并填写 draft_name / draft_fold_path / draft_root_path / 时间戳。
- ⚠️ macOS 剪映是沙盒应用，草稿和素材应放在 `~/Movies` 等可访问目录（Ceeon/videocut-skills `references/路径与沙盒.md`、Tigenix 代码）。
- ❓ 剪映 6+/11.x 打开保存后 `draft_content.json` 可能被加密（PyPI jianying-tool、capcut-cli 版本护栏）。只影响「改已有草稿」，本工具只新建草稿。

## 待真机确认
1. Mac 剪映：不登记索引时，重启后草稿是否出现；登记后是否立即出现。
2. Windows 剪映（当前版本）：是否需要索引；`globalSetting` 在改过草稿位置后的真实写法（引号、反斜杠、中文路径）。
3. Windows CapCut 路径。
