# Shotloom · 镜织 AI电影制作

Shotloom（镜织）是一套面向连续叙事 AI 视频的可复用制作插件，覆盖故事开发、剧本、场景规划、场景资产、分镜、Animatic、模型交接、镜头生成、连续性检查、剪辑后期与成片验收。

当前版本：**3.4.0**

## 适用范围

- 使用 Gemini、MiniMax 等模型制作连续叙事视频
- 从故事或剧本建立镜头表、Storyboard 与 Animatic
- 锁定角色、场景、固定设备、道具、摄影机与灯光状态
- 区分静态空间锁与环境动态，先做分层和无角色环境预演
- 用输出资产契约区分场景母版、独立图层、关键帧、分镜和正式视频
- 高效短片模式：变更审核、核心动作小样、两次失败换方法、C0–C4 停止标准
- 镜头目标与真实视频证据驱动：默认最小必要参考，按模型原生时长生成后选段
- 正常切镜使用前镜实际尾部的位置、方向、速度和作用区域设计入口
- `PREVIS / EDIT_READY / ACCEPTED` 分级，镜头可剪后立即替换时间线占位
- 多主体分治：主动作主体优先，次要主体按固定、遮罩、独立生成或实测联合生成处理
- 同场景连续动作、技术分段和真实尾帧续接
- 关键帧、视频片段、相邻镜头、声音与交付 QC

## 核心流程

1. 项目定义与故事开发
2. 正式剧本与剧本拆解
3. 场景计划
4. 场景空间预资产（`LAYOUT_APPROVED`）
5. 镜头表、Storyboard 与 Animatic
6. 正式场景资产包（`FINAL / ACCEPTED`，含动态环境分层与无角色预演）
7. 镜头生产五道关卡（含环境动态控制子关卡）
8. 视频生成、真实候选选段、实际尾部接镜与 `EDIT_READY`
9. 剪辑、声音、调色与成片 QC

正式关键帧和视频不得绕过场景资产包验收。相同场景与机位优先复用场景素材、Clean Plate、图层与空间资产，不得在每个关键帧中重新绘制整个场景。

## 安装

### ChatGPT 桌面版 / Codex

在 Codex CLI 中添加这个 GitHub 插件市场：

```bash
codex plugin marketplace add shaobrad639-cpu/shotloom-ai-film-production
```

然后：

1. 重新启动 ChatGPT 桌面版或新建 Codex 会话。
2. 打开 **Plugins**。
3. 选择 **Shotloom · AI电影制作**。
4. 安装 **Shotloom · 镜织 AI电影制作**。
5. 安装后新建对话再调用。

也可以克隆本仓库，在仓库目录中启动 ChatGPT 桌面版或 Codex；插件清单位于 `.agents/plugins/marketplace.json`。

## 调用

- ChatGPT：输入 `@shotloom`，或直接描述视频制作任务。
- Codex：输入 `$shotloom`，或从技能列表选择 Shotloom。

示例：

```text
@shotloom 根据这份剧本建立场景计划、场景资产清单、镜头表和 Animatic 制作计划。
```

```text
$shotloom 检查这些连续镜头的场景资产、空间关系、真实尾帧续接和剪辑连续性。
```

## 目录

```text
.agents/plugins/marketplace.json
plugins/shotloom-ai-film-production/
  plugin.json
  skills/shotloom/
    SKILL.md
    references/
    assets/templates/
    scripts/
    tests/
    examples/
```

## 验证

```bash
python3 -m unittest discover \
  -s plugins/shotloom-ai-film-production/skills/shotloom/tests \
  -p 'test_*.py'
```

当前版本包含 69 项自动化测试。

## 开源许可证

本项目采用 [MIT License](LICENSE)。允许个人及商业使用、复制、修改、合并、发布、分发、再许可和销售，但必须在软件副本或主要部分中保留原始版权与许可声明。

版权所有 © 2026 `shaobrad639-cpu`。

## 说明

Shotloom 提供制作流程、模板、检查机制和质量门槛，不替代导演、摄影、表演、剪辑与声音方面的创作判断。可测量、可复现的问题可以阻断放行；审美和创作判断应记录为评审意见，由创作者最终决定。
