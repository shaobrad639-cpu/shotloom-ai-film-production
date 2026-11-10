# 分层资产清单

- 场景素材包 ID / 版本：
- 唯一资产清单 / 文件校验报告：
- 场景机位变体：
- 场景制作方式：`EXACT_PLATE_COMPOSITE / STRUCTURAL_ANCHOR_CHECK / GEOMETRY_REPROJECTED`
- 场景是否来自批准底板、几何、材质或 Setup 渲染：是

| 图层 ID | 类型 | 稳定引用/版本 | 文件/SHA-256 | 可否变化 | 变化原因 | 遮挡顺序 | 状态 |
|---|---|---|---|---|---|---|---|
| | BACKGROUND_PLATE / GEOMETRY / RENDER | | | 按制作方式 | | | ACCEPTED |
| | FOREGROUND_OCCLUSION | | | 否 | | | ACCEPTED |
| | FIXED_EQUIPMENT | | | 否 | | | ACCEPTED |
| | CHARACTER | | | 是 | 角色动作 | | ACCEPTED |
| | MOVABLE_PROP | | | 按剧本 | | | ACCEPTED |
| | CONTACT_SHADOW | | | 是 | 接触/位置变化 | | ACCEPTED |
| | ENVIRONMENT_ANIMATION | | | 仅批准区域 | | | ACCEPTED |

- 分辨率 / 色彩空间：
- Setup / 摄影机 / 空间母版：
- 被角色遮挡区域是否已补全：
- 遮挡补全素材版本：
- 图层合成文件版本：
