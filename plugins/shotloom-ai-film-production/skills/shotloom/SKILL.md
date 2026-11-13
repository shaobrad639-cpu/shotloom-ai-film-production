---
name: shotloom
description: 按电影制作规范开发剧本、规划分镜、制作与验收连续叙事 AI 视频；用于故事与剧本、场景拆解、镜头表/Storyboard、Animatic、模型交接、摄影机语言、资产/空间连续性、技术分段续接和成片 QC。不用于无需时空连续性的孤立单图。
---

# Shotloom｜镜织 · AI电影制作

把 AI 生成当作电影制作中的一个执行环节，而不是让模型临场决定剧本、机位、资产和剪辑。项目从故事与剧本进入场景规划、镜头表、Storyboard 和 Animatic，锁定可剪辑方案后才生产正式镜头。正式生产采用“镜头目标驱动 + 资产装配驱动 + 真实视频证据驱动”：只准备实现镜头目标所需的最少输入，确保批准资产真实进入模型输入或受控合成，再由已选用视频的真实尾部状态驱动下一镜头。正式素材必须能回指剧本意图、镜头设计、已批准资产、实际输入和可观察证据；低成本预演可以使用占位资产，但必须明确不能继承为最终基线。

## 先判断从哪里开始

- 只有想法：从故事简报、梗概、Beat Sheet 和正式剧本开始。
- 已有剧本：先做剧本拆解、场景计划、镜头表和 Storyboard，不直接写生成提示词。
- 已有分镜或 Animatic：核对镜头 ID、时长、剪辑关系、声音节拍和资产需求，再进入五道关卡。
- 已有正式候选视频：从生成后验收、返工或后期交接开始，不倒推重做无关前期。

完整阶段、放行条件与产物见 [`end-to-end-production-workflow.md`](references/end-to-end-production-workflow.md)。五道关卡是正式镜头生产流程，不替代故事开发、剧本、Storyboard 或 Animatic。

## 先统一层级

- `sequence_id`：叙事段落。
- `scene_id`：同一时空中的场景；一个场景可以有多个镜头。
- `shot_id`：一次连续画面，是剪辑的基本单位。
- `setup_id`：摄影机、镜头、灯光和场面调度方案；同场景可有多个 Setup。
- `take_id`：同一 Shot/Setup 的一次执行版本。
- `segment_id`：因模型时长或平台限制拆出的技术生成分段；它不是新的镜头。

不得再把“同一场景”“同一镜头”“同一 Take”和“技术分段”混为一谈。只有剧本明确要求长镜头，或多个 `segment_id` 最终要无切点拼成同一 `shot_id + take_id` 时，才启用连续 Take 硬规则。

## 开始前

1. 读取已有材料并确定当前入口；缺少剧本时不要假装进入镜头生产，缺少 Storyboard/Animatic 时不要用正式生成代替预演。
2. 使用故事开发、剧本、拆解和场景计划建立前期包；先批准场景空间预资产，再制作镜头表、Storyboard 与 Animatic。镜头号、场景号和版本进入前期包后保持稳定。
3. 为本项目建立实际模型能力配置；记录真实提供商、模型 ID、验证日期、输入输出、原生时长、时长指令服从度、多主体身份可靠性与控制能力。Gemini、MiniMax 或其他模型的产品名不得替代能力证据。
4. 初剪与声音节拍成立后，将 Animatic 标记为 `LOCKED_FOR_PRODUCTION`；据此制作并验收正式场景资产包、角色和道具资产。可见动态环境必须先完成动态分层和无角色环境预演，再加入角色/物体。正式关键帧不得直接继承空间预资产或 Storyboard 占位图。
5. 运行 [`validate_scene_asset_package.py`](scripts/validate_scene_asset_package.py) 检查场景空间预资产或正式场景资产包；正式包必须闭合到已验收资产清单和文件 SHA-256。
6. 正式资产通过后，先用 [`shot-asset-map.json`](assets/templates/shot-asset-map.json) 建立全片镜头资产映射，为角色、场景、道具和新形态选择唯一正式基线；候选、预演和已替代版本不得混入正式生产。
7. 复制 [`shot-production-pass.json`](assets/templates/shot-production-pass.json)，填写 `sequence/scene/shot/setup/take/segment`、与上一镜头的关系及本轮目标；同时完成 `asset_usage_audit`，记录资产如何装配、模型实际收到什么，以及哪些约束只能事后验收。正常切镜也要引用上一镜实际视频尾部的位置、方向、速度和作用区域。
8. 先运行 [`validate_asset_manifest.py`](scripts/validate_asset_manifest.py) 校验资产清单与每个文件的 SHA-256，把它输出的 `manifest_digest_sha256` 写进通行证；再按阶段运行 [`validate_shot_pass.py`](scripts/validate_shot_pass.py)，放行前用 [`validate_sequence.py`](scripts/validate_sequence.py) 校验跨镜头链。Markdown 通行证只供阅读，JSON 是机器状态源。
9. 按需读取：
   - 端到端制作、剧本/分镜/Animatic 与模型适配：[`end-to-end-production-workflow.md`](references/end-to-end-production-workflow.md)
   - 层级、覆盖拍摄、剪辑与摄影语言：[`film-production-structure.md`](references/film-production-structure.md)
   - 五关执行标准：[`five-gates.md`](references/five-gates.md)
   - 资产与版本：[`asset-identity-lock.md`](references/asset-identity-lock.md)
   - 镜头资产映射、装配、实际模型输入和生成后比对：[`asset-assembly-and-usage.md`](references/asset-assembly-and-usage.md)
   - 场景、设备、触达与摄影机空间：[`spatial-lock.md`](references/spatial-lock.md)
   - 场景空间预资产与正式场景资产包：[`scene-asset-production.md`](references/scene-asset-production.md)
   - 独立场景、角色/道具层、关键帧和正式镜头的输出身份：[`output-asset-contract.md`](references/output-asset-contract.md)
   - 固定环境与动态环境边界：[`environment-animation-lock.md`](references/environment-animation-lock.md)
   - 固定底板、3D/2.5D 与关键帧：[`layered-keyframe-production.md`](references/layered-keyframe-production.md)
   - 同一连续 Take 的技术分段：[`one-take-continuity.md`](references/one-take-continuity.md) 与 [`actual-tail-continuation.md`](references/actual-tail-continuation.md)
   - 相邻镜头、返工与版本：[`continuity-and-versioning.md`](references/continuity-and-versioning.md)
   - 模型交接与重试：[`generation-handoff.md`](references/generation-handoff.md)
   - 最小必要输入、模型原生时长、真实视频接镜与 `EDIT_READY`：[`video-evidence-driven-workflow.md`](references/video-evidence-driven-workflow.md)
   - 短片的轻量路线、小样、换方法和停止标准：[`efficient-production-mode.md`](references/efficient-production-mode.md)
   - 前期与成片 QC：[`preproduction-and-quality-control.md`](references/preproduction-and-quality-control.md)
   - 连续 Take 示例：[`shot-03-case.md`](references/shot-03-case.md)

## 镜头生产五道关卡

只有镜头表、Storyboard、Animatic 与正式场景资产包达到当前项目所需成熟度，正式镜头才进入五道关卡。概念测试可以缩减前期产物并使用已批准的场景空间预资产，但必须标记为 `PREVIS`，不得冒充正式放行。

状态只使用 `NOT_RUN / IN_PROGRESS / PASS / BLOCKED / N/A`。关键未知、互相冲突或无法验证的生产条件才 `BLOCKED`；低风险创作选择可登记为假设并在 Previs 验证，不要把所有空白都当成阻断项。

短片或轻量项目可选择 `EFFICIENT_SHORT`：五关仍是质量底线，但后续轮次只复核变更及受影响项目；L2–L4 先做核心风险小样；同一方法失败两次必须换路线；验收按 C0–C4 分级并立即回填时间线。具体规则见 [`efficient-production-mode.md`](references/efficient-production-mode.md)。

1. **剧本、剪辑与动作审核**：明确场景目的、镜头目的、动作节拍、入口/出口状态、时长、与前后镜头的剪辑关系，以及为什么需要这个景别和机位。允许同场景切镜、反打、插入镜头和时间省略，但必须有编辑意图并通过轴线、视线、屏幕方向和动作匹配检查。
2. **资产、场景、空间与道具审核**：锁定角色、场景、固定设备和道具身份，并建立 Shot 级资产使用映射；记录每项可见资产的唯一批准版本、装配位置、模型输入或合成方式，以及出现、移动、使用、遮挡与离画原因。新出场或变形实体必须有批准视觉依据。涉及固定设备或角色交互时核对世界坐标、相对尺寸和可触达性；没有此类内容时可 `N/A` 并说明。其强制子关卡 `gate_2b_environment_dynamics` 依次检查场景母版、动态分层、无角色环境预演和角色/物体反应计划；可见的水、云、雾、雨雪、烟火、植被、蒸汽或光照动态未通过时不得正式生成。
3. **场面调度、角色、摄影机与声音审核**：核对角色站位、视线、左右手、动作路径、180 度轴、景别、焦距或视场角、景深/焦点、摄影机位移/旋转/变焦、速度曲线、起止状态、视差预期和运镜动机；同时规划对白、环境声、动作声和音乐剪辑点。
4. **关键状态与 Previs/Animatic**：默认只准备一张完整首帧和镜头交接；只有精确落点、接触、转换或出口状态确实需要、且模型实测支持时，才增加尾帧或中间关键状态。验证动作时长、构图、遮挡、物理接触、摄影机轨迹和剪辑点；含动态环境时还要验证环境自身运动及动作驱动的环境反应。只有同一连续 Take 的后续技术分段，才必须把上一分段实际视频的真实尾帧作为生成起点。
5. **生成前放行与生成后验收**：先批准输出资产契约，再核对资产使用记录与模型输入回执。所有可见基线必须明确是直接输入、装配进关键画面、视频参考、固定合成、局部编辑、独立生成或后期合成；模型没收到的约束必须说明替代控制与验收方法。按模型已验证的原生时长生成，时长指令不可靠时从候选中选择实际可用区间。生成后必须把结果与批准角色、场景、道具和新形态逐项比对，并检查主体动作、环境运动、摄影机运动及主体与环境因果。可剪区间通过核心检查后标记 `EDIT_READY`，立即替换工作时间线占位，并提取真实尾部证据用于下一镜头；最终音画与交付质量通过后才 `ACCEPTED`。

## 不可误用的规则

- **同一场景不等于一镜到底。** `EDITORIAL_SHOT` 允许正常剪辑；`CONTINUOUS_TAKE` 才要求零切点。
- **真实尾帧只用于连续 Take 的技术分段。** 正常切镜使用前一镜头的实际尾部状态做连续性证据，但新镜头首帧不必复制上一帧像素。
- **Pixel Lock 不等于所有静态画面都零差异。** 直接复用同一固定底板时可要求保护区 100% 像素一致；重新渲染、胶片颗粒、光照呼吸或批准的环境动态采用静态锚点、几何、色彩和运动容差检查。
- **场景资产复用不等于禁止渲染。** 禁止的是无控制地让模型重新想象场景。批准的固定底板、深度分层、2.5D、3D 场景、局部修复或新 Setup 渲染均可使用，但必须继承同一场景身份与空间母版。
- **分层角色不是唯一制作方法。** 固定底板合成优先使用独立角色/道具层；角色 Rig、3D 渲染、受控局部编辑或能证明连续性的其他方法同样允许。
- **固定机位不等于静止环境。** 摄影机空间状态可锁定，水、云、雾、雪、火、植被、蒸汽和光照仍可按登记方向、强度和相位演化。
- **场景母版不等于最终动态背景。** 母版锁静态空间；动态层要先在无角色预演中通过，再与角色/物体合成。不能靠正式生成时整图重绘临时制造环境运动。
- **提示词不等于输出资产契约。** 提示词描述内容，契约锁定交付物身份。需要独立场景、角色层或道具层时，不得接受综合海报、说明文字、额外角色或未批准背景。
- **轻量制作不等于降低连续性标准。** 它减少重复审核和低收益精修，不允许忽略身份、空间、动作因果、环境反应或技术接缝。
- **参考图视频不是唯一默认路线。** 按镜头风险选择直接参考视频、底板合成、关键帧引导或 Rig/3D；采用能达到交付标准的最低复杂度方法。
- **关键帧数量不代表控制质量。** 默认采用最小必要参考；只有精确出口或模型验证需要时才增加尾帧和中间帧。
- **提示秒数不等于实际时长。** 记录模型原生时长并在剪辑中选用目标区间；只有能力测试通过才依赖精确时长控制。
- **多主体不默认联合生成。** 指定主动作主体；易漂移的配角、设备或小物体优先固定、遮罩、独立生成或合成，联合生成必须有身份可靠性证据。
- **资产已批准不等于资产已使用。** 资产清单证明版本，资产使用记录证明它进入了模型输入或受控合成；两者都通过才能正式生成。
- **首帧包含资产不等于持续约束成立。** 必须记录首帧由哪些批准资产装配、模型实际收到哪些输入，以及输出如何与基线比对。
- **文字描述不能替代视觉身份依据。** 新角色、变形终态、场景母版和关键道具必须通过视觉输入、装配关键状态或受控合成参与生产。

## 摄影机交接最小字段

每个正式镜头至少写明：`setup_id`、景别、摄影机高度与角度、焦距或等效视场角、帧率/快门或运动模糊依据、曝光/白平衡、焦点/景深、起止构图、`position_moves`、平移类型、旋转类型、镜头焦距变化、运动方向/路径、速度曲线、主体锁定方式、视差预期、运镜动机和剪辑关系。不要只写“电影感”“推近一点”或“镜头动起来”。

## 必备产物按风险裁剪

- 所有正式镜头：JSON 通行证、镜头/Setup 设计、状态转换、资产引用、资产使用记录、模型实际输入清单、关键状态或 Previs、生成交接和验收记录。
- 有复杂场景或道具：场景/道具台账、空间母版、触达或遮挡证据。
- 有可见动态环境：环境动态分层清单、无角色环境预演、相位基线、反应耦合计划和完整镜头证据。
- 每次正式生成：已批准的 `generation-output-contract.json` 及校验报告。
- `EFFICIENT_SHORT`：制作路线与变更审核；L2–L4 的核心风险小样；Sequence 完成度看板。
- 固定底板合成：图层清单、允许变化蒙版和 Pixel Lock/静态锚点报告。
- 移动摄影机：轨迹、焦距/焦点、几何或深度依据及重投影/视差验证。
- 连续 Take 技术分段：真实尾帧验收、接缝前后帧、摄影机和动作相位续接。
- 正常切镜：轴线、视线、屏幕方向、动作匹配、景别变化和声音桥检查。

## 状态与放行

- `DRAFT`：设计中。
- `BLOCKED`：关键条件缺失或冲突。
- `READY_FOR_PREVIS`：可制作低成本预演，不代表可生成正式素材。
- `PREVIS`：动作或技术路线的小样已经形成，仍不是正式可剪镜头。
- `READY_FOR_RELEASE`：正式输入完整，等待机器校验。
- `GREENLIT`：允许生成正式素材。
- `EDIT_READY`：真实候选区间通过核心检查、已回填时间线并提取尾部证据；允许把轻微问题延后统一精修。
- `ACCEPTED / REJECTED / SUPERSEDED`：验收通过、拒绝或被新版本替代。

## 校验命令与证据链

```bash
# 0) 前期包：剧本拆解、场景计划、镜头表、Animatic 与实际模型能力
python3 scripts/validate_preproduction.py \
  --script-breakdown <script-breakdown.json> \
  --scene-plan <scene-plan.json> \
  --scene-asset-package <scene-asset-package.json> \
  --shot-list <shot-list.json> \
  --animatic <animatic-timeline.json> \
  --model-profile <model-capability-profile.json> \
  --target production

# 0a) 场景资产：Storyboard 前检查空间预资产；正式关键帧前检查最终资产包
python3 scripts/validate_scene_asset_package.py <scene-asset-package.json> --target layout
python3 scripts/validate_scene_asset_package.py <scene-asset-package.json> --target final \
  --manifest <资产清单.json> --root <项目资产根目录>

# 1) 资产清单：文件存在、逐文件 SHA-256、引用唯一性；输出 canonical digest
python3 scripts/validate_asset_manifest.py <资产清单.json> --root <项目资产根目录>

# 1a) 输出资产契约：交付物类型、素材隔离、必须/禁止元素和技术格式
python3 scripts/validate_output_contract.py <输出资产契约.json>

# 2) 通行证：previs 只查关卡 1-3；release/edit-ready/acceptance 必须闭合资产证据
python3 scripts/validate_shot_pass.py <通行证.json> --target previs
python3 scripts/validate_shot_pass.py <通行证.json> --target release \
  --manifest <资产清单.json> --root <项目资产根目录> --stamp
python3 scripts/validate_shot_pass.py <通行证.json> --target edit-ready \
  --manifest <资产清单.json> --root <项目资产根目录> --stamp
python3 scripts/validate_shot_pass.py <通行证.json> --target acceptance \
  --manifest <资产清单.json> --root <项目资产根目录> --stamp

# 2b) 迁移：旧版校验器盖过章的通行证重新盖章（重新校验，只更新版本与时间戳）
python3 scripts/validate_shot_pass.py <通行证.json> --target release \
  --manifest <资产清单.json> --root <项目资产根目录> --restamp
python3 scripts/restamp_passes.py <项目目录> --dry-run   # 先看哪些会重盖
python3 scripts/restamp_passes.py <项目目录>             # 批量重盖

# 3) 跨镜头连续性：重复通行证、前序镜头、技术分段链、清单摘要一致性
python3 scripts/validate_sequence.py <通行证目录> --manifest-digest <manifest_digest_sha256>

# 4) 改动校验器后必须跑单测
python3 -m unittest discover -s tests -p 'test_*.py'
```

- 资产证据闭合包含两层：`asset_identity_lock` 证明版本、文件与 SHA 正确；`asset_usage_audit` 证明每个可见基线实际进入模型输入或受控合成，并记录平台实际输入回执。任一层缺失都会阻断正式生成。
- release/edit-ready/acceptance 缺少 `--manifest` 会直接 `BLOCKED`；`--allow-unverified` 只用于离线演示，不得用于正式交付。
- `--stamp` 才会写入 `shot.status`、对应阶段的 `validator_version` 与时间戳；手工改 JSON 会与版本校验冲突。
- 被旧版校验器盖过章的 `GREENLIT/EDIT_READY/ACCEPTED` 通行证用 `--restamp` 迁移：它按当前证据链重新校验，通过后只刷新 `validator_version/validated_at`，不降低已过关卡；证据不足时 `BLOCKED`，不会强行盖章。批量迁移用 `scripts/restamp_passes.py`，先 `--dry-run` 再实际执行。
- 只有 `REJECTED` / `SUPERSEDED` 可以通过 `--reopen --reason "..."` 回到 `DRAFT` 重做；其它状态不应手改 JSON。
- 校验器版本以脚本内 `VALIDATOR_VERSION` 为准，插件清单版本只用于分发；发布时两者必须同步升级并在提交说明里写清楚。
- 同一缺陷连续出现两次，或同一未改变生产条件的方案达到三轮（`current_round >= max_rounds`），停止抽卡并退回造成问题的关卡。返工优先级为：安全裁切 → 局部修复 → 合成/剪辑修复 → 重做关键状态 → 重生当前技术分段或 Shot；任何改变剧情状态、空间、资产身份或动作相位的修复都必须重新过关。

## 模板索引

- 故事与剧本：`story-development.md`、`screenplay.md`、`script-breakdown.json`
- 场景与分镜：`scene-plan.json`、`scene-asset-package.json`、`shot-list.json`、`storyboard-sheet.md`、`animatic-timeline.json`
- 模型能力：`model-capability-profile.json`；每个项目按实际 Gemini、MiniMax 或其他模型版本填写
- 启动：`project-brief.md`、`shot-asset-map.json`、`asset-usage-record.md`、`generation-brief.md`、`generation-output-contract.json`、`independent-preflight-review.md`
- 台账：`character-ledger.md`、`prop-ledger.md`、`scene-ledger.md`、`rework-version-log.md`
- 空间与场景：`spatial-lock-check.md`、`environment-animation-lock.md`、`layer-manifest.md`
- 连续性与关键帧：`adjacent-shot-continuity.md`、`one-take-continuity.md`、`actual-tail-validation.md`、`keyframe-animatic-validation.md`
- 合成与验收：`pixel-lock-check.md`、`edit-ready-review.md`、`acceptance-sampling.md`
- 高效制作：`sequence-progress-board.md`
- 机器可读：`shot-production-pass.json`、`asset-manifest.json`；阅读版：`shot-production-pass.md`
- 示例：`examples/shot-03/`（通过 `--target release` 的完整证据链，以及单点阻断样例）

