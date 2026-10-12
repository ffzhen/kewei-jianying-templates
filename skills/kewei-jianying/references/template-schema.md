# template.json 字段说明

| 字段 | 说明 |
|---|---|
| id / name / version | 模板标识、中文名、版本 |
| source_preset | 来自可为AI 内部的哪个预设（original / tech / warm / business） |
| width, height, fps | 画布，默认 1080×1920、30fps |
| caption_style | 字幕样式（见下） |
| title_style | 标题样式，结构同字幕，多一个 line_count（标题行数） |
| background_music_volume, audio_volume | 0–1，只作参考，脚本不处理音频 |

## caption_style / title_style
- `base_style`
  - `font_type`：剪映字体名（俪金黑、文轩体、宋体、黑体）
  - `size`：剪映字号
  - `color`：RGB，每个分量 0–1
  - `bold`：是否加粗
  - `align`：0=左，1=中，2=右
  - `auto_wrapping`：自动换行
  - `max_line_width`：最大行宽，占画面宽度的比例（0–1）
  - `line_spacing`：行间距
  - `scale_x` / `scale_y`：横向、纵向缩放
- `highlight_style`：关键词高亮的 `color`、`size`、`bold`
- `shadow_style`：阴影的 `alpha`、`color`、`diffuse`（模糊度）、`distance`（距离）、`angle`（角度）
- `background_style`（可为 null）：文字底色
  - `color`：十六进制颜色
  - `alpha`：不透明度
  - `height` / `width`：底色高度、宽度
  - `horizontal_offset` / `vertical_offset`：左右、上下间隙
  - `round_radius`：圆角（脚本会截断到 0–1）
  - `style`：1 或 2
- `transform_y`：垂直位置，−1（底）到 1（顶）
- `position`：top / center / bottom（只作说明）
