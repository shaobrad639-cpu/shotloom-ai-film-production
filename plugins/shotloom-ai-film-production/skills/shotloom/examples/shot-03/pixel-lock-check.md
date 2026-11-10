# 镜头 03 Pixel Lock 检查

| 字段 | 内容 |
|---|---|
| 场景 / Take / 分段 | DEMO_EP01_SC01 / TK01 / SG03 |
| 模式 | EXACT_PLATE_COMPOSITE |
| 背景底板 | SET-001_C2_BACKGROUND_PLATE_v003 |
| 图层清单 | layer-manifest.md |
| 允许变化蒙版 | first-to-peak / peak-to-last v001 |
| 最低保护区占比 | 0.5 |

| 基准帧 | 待检帧 | 保护区占比 | 匹配率 | 变化保护像素 | 结果 |
|---|---|---:|---:|---:|---|
| first_v003 | peak_v003 | 0.71 | 1.0 | 0 | PASS |
| peak_v003 | last_v003 | 0.68 | 1.0 | 0 | PASS |

固定设备、未动作道具和背景纹理均在保护区。允许变化只覆盖主角、模块运动轨迹、接触阴影和必要遮挡变化。结论：`PASS`。
