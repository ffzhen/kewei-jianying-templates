复制下面这段，粘贴到 WorkBuddy（或 Claude Code / Codex / CodeBuddy）里：

```
帮我在这台电脑上用「可为AI 开源剪映模板」生成一个剪映草稿：
1. 先运行 kewei-jianying --version 检查是否已安装；没有就安装：
   uv tool install "git+https://github.com/ffzhen/kewei-jianying-templates"
   （没有 uv 就用 pipx install 或 python3 -m pip install --user 同一个地址）
2. 运行 kewei-jianying install-skill 安装技能，然后按技能 kewei-jianying 的步骤来：
   kewei-jianying doctor 自检 → 找不到剪映草稿目录就问我 → kewei-jianying list 选模板 → kewei-jianying build 生成草稿
3. 我的内容：【在这里粘贴口播稿，或写 SRT 字幕文件路径】
   模板：【知识口播 / 科技解析 / 门店种草 / 商务专业，不填你帮我选】
4. 完成后告诉我草稿名称和位置，我打开剪映接着改。
```
