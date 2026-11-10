# 镜头 03 分层资产清单

- 场景素材包：`SET-001_C2_SCENE_ASSET_BUNDLE_v003_ACCEPTED`
- 唯一资产清单：`DEMO_EP01_asset-manifest_v004_ACCEPTED.json`；文件与 SHA-256 校验 `PASS`
- 场景机位变体：`SET-001_C2_v003`
- 关键帧场景来源：`EXISTING_SCENE_ASSET`
- 关键帧重新生成、补画或重新采样场景：否

| 图层 ID | 类型 | 资产版本/文件 | 可否变化 | 变化原因 | 遮挡顺序 | 状态 |
|---|---|---|---|---|---|---|
| L01 | BACKGROUND_PLATE | SET-001_C2_BACKGROUND_PLATE_v003 | 否 | 无 | 最后 | LOCKED |
| L02 | FIXED_EQUIPMENT | SET-001_C2_FIXED_v003 | 否 | 无 | 背景上方 | LOCKED |
| L03 | CHARACTER | CHAR-001_SH03_POSES_v003 | 是 | 走近、握持、取下 | 设备前/后按空间关系 | APPROVED |
| L04 | MOVABLE_PROP | PROP-MODULE-001_v002 | 是 | 从设备接口取下 | 与右手绑定 | APPROVED |
| L05 | CONTACT_SHADOW | CHAR-001_SH03_SHADOW_v002 | 是 | 位置和接触变化 | 角色下方 | APPROVED |
| L06 | FOREGROUND_OCCLUSION | SET-001_C2_COUNTER_FG_v003 | 否 | 无 | 最前 | LOCKED |

- 分辨率 / 色彩空间：1920×1080 / sRGB
- 固定机位 / 空间母版：C2 / SET-001_SPACE_v002
- 被角色遮挡区域是否已补全：是
- 遮挡补全素材：`SET-001_C2_OCCLUSION_COMPLETION_v002`
- 图层合成文件版本：DEMO_EP01_SH03_COMPOSITE_v003
