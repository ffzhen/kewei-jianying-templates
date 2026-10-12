#!/usr/bin/env bash
# 端到端：全新 venv 安装本地包 → doctor → 4 模板 + 30 动效 + 素材草稿 → 校验
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"; W="$(mktemp -d)"
python3 -m venv "$W/venv" && "$W/venv/bin/pip" -q install "$R"
K="$W/venv/bin/kewei-jianying"; export KEWEI_JIANYING_DRAFT_ROOT="$W/drafts"; mkdir -p "$W/drafts"
$K --version && $K where && $K doctor
(cd "$R/tests" && PATH="$W/venv/bin:$PATH" "$W/venv/bin/python" -W ignore -m unittest test_detect_place)
diff -r "$R/skills/kewei-jianying" "$R/src/kewei_jianying/skill" >/dev/null || { echo "skills/ 与包内 skill/ 不一致"; exit 1; }
for t in $($K list --json | "$W/venv/bin/python" -c "import json,sys;print(' '.join(x['id'] for x in json.load(sys.stdin)['templates']))"); do
  $K build -t "$t" --srt "$R/examples/sample.srt" -k "$R/examples/keywords.json" --title "把字幕模板交给Agent" -n "t-$t" --json; done
for m in $($K list --json | "$W/venv/bin/python" -c "import json,sys;print(' '.join(json.load(sys.stdin)['motions']))") none; do
  $K build -t zhishi-koubo --srt "$R/examples/sample.srt" -k 剪映草稿,Agent -n "m-$m" -m "$m" --json >/dev/null; done
if command -v ffmpeg >/dev/null; then
  ffmpeg -loglevel error -y -f lavfi -i testsrc=size=1080x1920:rate=30 -f lavfi -i sine -t 8 -pix_fmt yuv420p -shortest "$W/v.mp4"
  ffmpeg -loglevel error -y -f lavfi -i sine=frequency=220 -t 10 "$W/bgm.mp3"
  $K build -t mendian-zhongcao --text "门店也能天天更新。一句话生成剪映草稿！" --video "$W/v.mp4" --bgm "$W/bgm.mp3" -n media --json >/dev/null
fi
"$W/venv/bin/python" "$R/tests/validate_draft.py" "$W"/drafts/*
[ -z "$(ls -A "$W/drafts" | grep "^\.kewei-build-" || true)" ] || { echo "临时目录未清理"; exit 1; }
echo "ALL OK ($W)"
