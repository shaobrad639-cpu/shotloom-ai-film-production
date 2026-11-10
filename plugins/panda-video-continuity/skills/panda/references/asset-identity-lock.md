# 资产身份与版本锁定

## 锁定单位

每个进入关键帧、Animatic 或视频模型的输入都必须有资产身份证：稳定 `asset_id`、类型、版本、生产引用 `reference`、文件路径、SHA-256 和状态。只有 `ACCEPTED` 可以进入生产。文件名、提示词描述或“上一张图”都不能单独证明资产身份。

资产清单覆盖当前镜头实际使用的角色、场景、空间、摄影机、道具、关键状态及所需蒙版/几何。不存在的资产类型不必建立空记录。使用 `assets/templates/asset-manifest.json` 建立唯一清单，禁止为同一项目建立互不一致的副本。

## 四重锁定

1. **身份锁定**：稳定 ID、版本、批准状态与 SHA-256 防止同名替换和错误参考。
2. **空间锁定**：固定设备与摄影机使用世界坐标、旋转、尺寸、比例和容差。
3. **状态锁定**：道具与角色记录入口状态、变化动作和出口状态；存在、可见和使用分开。
4. **像素/几何锁定**：静态机位复用相同场景像素；移动机位复用批准的深度、2.5D 或 3D 几何与材质。

适用的锁定项必须通过；不适用项写明理由。参考图相似不能替代身份和状态证据，像素相同也不能替代错误的空间数据。

## 文件校验

在生成前运行：

```bash
python3 scripts/validate_asset_manifest.py project/asset-manifest.json --root project
```

脚本逐项检查文件存在、清单状态、引用唯一性和实际 SHA-256。任一文件缺失、内容与清单不符、版本重复、状态非 `ACCEPTED` 时输出 `BLOCKED`。校验成功后保存输出作为 `manifest_validation_reference`，并把输出的 `manifest_digest_sha256` 写入镜头通行证 `asset_identity_lock.manifest_digest_sha256`。

该摘要不是文件字节的 SHA-256，而是清单内容的 canonical digest：`json.dumps(manifest, sort_keys=True, separators=(",", ":"))` 后取 SHA-256，因此重排缩进或字段顺序不会改变摘要，改内容一定改变摘要。

## 生产引用闭合

镜头通行证中以下引用必须能在资产身份锁中找到完全相同的 `reference`：

- `asset_baselines` 中的角色、场景和道具；
- `scene_asset_lock` 中的场景素材包、机位变体、背景/几何、前景遮挡、固定设备和遮挡补全；
- 空间母版版本；
- 所有首帧、峰值帧和尾帧；
- Pixel Lock 的所有允许变化蒙版。

不得通过相似名称、未带版本的别名或文件软替换绕过。这条规则由 `validate_shot_pass.py --manifest` 机器执行：通行证的 `asset_identity_lock.assets` 必须逐条等于清单条目，上述引用必须全部命中清单，摘要必须等于清单的 canonical digest。

```bash
python3 scripts/validate_shot_pass.py project/shot-pass.json --target release \
  --manifest project/asset-manifest.json --root project
```

引用内容变化时，创建新版本、重新计算 SHA-256、重新审批，并对依赖它的关键帧和视频执行失效传播。

## 各类资产的生产方式

- 场景和固定设备：复用批准的底板、几何、材质或 Setup 渲染，不得无控制地重新想象。
- 角色：可使用透明姿态层、Rig、3D 渲染或受控局部编辑；姿态可变，身份特征不可漂移。
- 活动道具：数量和身份固定，只能通过台账登记动作改变位置、可见性或持有者。
- 摄影机：按 Setup 锁定起止参数；连续运动使用批准轨迹，不能反向移动场景资产迎合构图。
- 关键帧：锁定后作为视频生成输入；局部修改必须产生新版本和新校验值。
- 真实尾帧：来自实际成片并单独验收；成为同一连续 Take 后续 Segment 入口时登记为新的 `ACCEPTED` 资产。

## 阻断与返工

以下任一情况立即阻断：资产不在清单；状态不是 `ACCEPTED`；文件或校验值缺失；SHA-256 不匹配；通行证引用与清单不一致；同一引用对应多个不同文件；在原路径覆盖文件却未升级版本；关键帧携带重新生成的场景；使用被拒绝或已替代资产。

资产内容变化一律产生新版本。角色/场景/空间基线变化按 C3 处理；关键帧、道具状态或机位引用变化至少按 C2 处理。旧版本保留但标记 `SUPERSEDED`，不得删除后让新文件占用旧引用。
