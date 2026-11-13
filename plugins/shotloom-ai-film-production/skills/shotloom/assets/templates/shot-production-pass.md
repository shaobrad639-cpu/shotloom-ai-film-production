# 镜头生产通行证

| 字段 | 内容 |
|---|---|
| sequence / scene / shot | |
| setup / take / segment | |
| 连续性模式 | EDITORIAL_SHOT / CONTINUOUS_TAKE |
| 与上一镜头关系 | SCENE_START / EDITORIAL_CUT / CONTINUOUS_SEGMENT / INDEPENDENT |
| 通行证版本 / 状态 | v001 / DRAFT |
| 镜头目的 / 时长 | |
| 入口状态 / 动作节拍 / 出口状态 | |

## 制作策略

| 字段 | 内容 |
|---|---|
| 模式 / 风险等级 | STANDARD / EFFICIENT_SHORT；L1/L2/L3/L4 |
| 制作路线 / 版本 | DIRECT_REFERENCE_VIDEO / PLATE_PLUS_VIDEO_COMPOSITE / KEYFRAME_GUIDED_VIDEO / RIG_OR_3D_CONTROLLED |
| 路线理由 | |
| 继承锁定项 / 本轮变更 / 影响检查 | |
| 是否全量复核 | |
| 核心风险小样 / 时长 / 证据 | |

## 五道关卡

| 关卡 | 状态 | 证据或阻断原因 | 最小修正 |
|---|---|---|---|
| 1. 剧本、剪辑与动作 | | | |
| 2. 资产、场景、空间与道具 | | | |
| 2B. 环境动态控制（无角色预演） | | | |
| 3. 调度、角色、摄影机与声音 | | | |
| 4. 关键状态与 Previs/Animatic | | | |
| 5A. 生成前放行 | | | |
| 5B. 生成后验收 | | | |

## 剪辑与连续性

| 检查项 | 结果 | 证据 |
|---|---|---|
| 轴线、视线、屏幕方向 | | |
| 动作匹配 / 时间省略 | | |
| 光线、色彩、天气 | | |
| 对白、环境底、音乐/声音桥 | | |
| 连续 Segment 的真实尾帧（如适用） | | |

## 摄影机计划

| 项目 | 内容 |
|---|---|
| setup_id / 景别 / 高度 / 角度 | |
| 焦距或 FOV / 帧率与快门 / 曝光与白平衡 | |
| 焦点 / 景深 | |
| position_moves | true / false |
| translation / rotation / lens_change | |
| 路径 / 方向 / 速度曲线 | |
| 起止构图 / 主体锁定 / 视差预期 | |
| 运镜动机 / 后期合成 | |

## 场景与画面锁定

- 资产清单 / 场景包 / 空间母版：
- 制作方式：EXACT_PLATE_COMPOSITE / STRUCTURAL_ANCHOR_CHECK / GEOMETRY_REPROJECTED（`scene_asset_lock.production_method` 不接受 N/A；不涉及画面锁定时在 `picture_lock.mode` 填 N/A）
- 图层、蒙版、静态锚点或几何证据：
- 环境动态与静态保护边界：
- 环境动态分层清单 / 无角色环境预演 / 相位基线：
- 角色或物体 → 环境反应耦合：
- 道具出现/变化/离画因果：
- 触达、遮挡和固定设备检查；不适用原因：

## 生成输出资产契约

| 字段 | 内容 |
|---|---|
| 契约 / 校验报告 | |
| 交付物类型 | VIDEO_SHOT |
| 必须元素 / 禁止元素 | |
| 背景模式 / Alpha / 图层角色 | |
| 允许烘焙元素 / 素材隔离 | |
| 画幅 / 分辨率 / 色彩空间 / 文件格式 | |
| 文字策略 | FORBIDDEN / REQUIRED / ALLOWED |

## 关键状态与验收

| 角色 | 时间码 | 角色/道具状态 | 摄影机/焦点 | 声音 | 证据引用 |
|---|---|---|---|---|---|
| first / last | | | | | |

| 完整镜头运动检查 | 结果 | 证据或 N/A 依据 |
|---|---|---|
| 角色/主体动作 | | |
| 环境运动 | | |
| 摄影机运动 | | |
| 角色/主体与环境因果 | | |

- 关键问题：
- 已登记假设：
- 放行结论 / 校验器版本：
- 成片结论 / 接受版本 / 台账写回：
- C0/C1 清零 / C2 结论 / C3 全片精修 / C4 接受：
- 时间线替换与 Sequence/全片播放证据：

> 正式状态以同版本 JSON 通行证及校验器结果为准。

