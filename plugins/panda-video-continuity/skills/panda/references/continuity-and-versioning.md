# 连续性、返工与版本

## 两类相邻关系

### 正常切镜

比较故事时间、角色站位/视线/情绪、屏幕方向、左右手与持物、道具状态、轴线、景别变化、动作匹配、光线/色彩和声音桥。前一镜头实际尾部是证据，但新镜头不复制上一帧像素。

### 连续 Take 技术分段

建立 `前一 Segment 实际视频 → 已验收真实尾帧/尾部窗口 → 当前 Segment 首帧` 映射；时间间隔、编辑切点为 0，并继承摄影机、动作、声音和环境相位。

## 返工等级

- `C0` 文案/标注。
- `C1` 局部外观，不改变状态或剪辑。
- `C2` Shot 连续性、动作、机位、持物或技术接缝。
- `C3` 角色/场景/空间基线。
- `C4` 剧本、镜头结构或剪辑方案。

冻结问题版本，创建新版本，不覆盖原文件。依赖链按实际关系记录；只有受影响的下游资产失效，不把无关镜头一并返工。

## 重试

同一缺陷连续两次或同一生产条件达到三轮时熔断。重试必须改变导致失败的条件，例如参考、动作拆分、模型、关键帧、摄影机或合成方法；只改随机种子不算修订。

计数口径（与校验器一致）：

- `current_round` 是已经用完的轮次，`max_rounds` 是允许的总轮次；`current_round >= max_rounds` 即熔断，所以第 3 轮结束、上限 3 轮时不能开第 4 轮。
- `same_defect_count` 是同一缺陷已经发生的次数，`same_defect_limit` 是允许次数；达到即熔断。
- `current_round > 0` 时必须填写 `repair_ladder_step` 和 `changed_production_condition`，证明这次重试确实换了生产条件。
- 被拒绝或已被替代的通行证不能原地复活：用 `validate_shot_pass.py <pass.json> --reopen --reason "..."` 回到 `DRAFT`，再带新理由重新过关。


## 校验器版本迁移

通行证里的 `release.validator_version` / `acceptance.validator_version` 是“谁盖的章”。校验器升级后，旧版本盖章的 `GREENLIT/ACCEPTED` 通行证属于“旧章”，不能直接当作已通过新校验：

- 不迁移就用当前校验器重跑 release/acceptance，会报 `validator_version: expected <当前版本>`，这是故意的，防止旧证据链冒充新结论。
- 迁移用 `--restamp`：按当前证据链重新校验全部关卡（含资产清单、文件 SHA、引用闭合），通过后只把 `validator_version` 和 `validated_at` 换成当前值，`shot.status` 不降级；任何一条证据不成立都会 `BLOCKED`，不会强行盖章。
- 批量迁移用 `scripts/restamp_passes.py <项目目录>`，先加 `--dry-run` 看清单；缺 `asset-manifest.json` 的通行证会被跳过并列出原因。
- 不要手工把版本号改成新值：手工改出的章没有校验记录，下一个人无法判断它按什么规则通过。
