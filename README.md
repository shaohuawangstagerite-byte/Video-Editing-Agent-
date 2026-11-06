# 剪辑 Agent

使用 OpenCode 分析抽帧并制定剪辑清单，用 FFmpeg 裁切、加速、拼接和添加阶段标题，完成后检查成片。

准备 Windows PowerShell、Python 3.9+、Git for Windows、FFmpeg（含 ffprobe）和 OpenCode，确保相关命令可用。自备支持图片的模型连接与标题字体；模型配置保存在本机，包含 `model`、`enabled_providers`、`provider`。

在项目根目录打开 PowerShell，按需创建本地目录：素材放入 `inputs/<task-id>/`，任务说明写入 `outputs/<task-id>/task-brief.md`。说明哪些操作需要加速、哪些成果原速展示，以及标题和成片要求；未指定的编码参数使用项目默认值。输入须同时包含音视频轨，原始素材只读。

先用 FFmpeg 抽帧，将联系表放在 `outputs/<task-id>/tmp/overview.jpg`，确认有权发送至模型服务。抽帧应能看清主要操作和最终成果，信息不足时补充阶段边界附近的画面。替换下面的任务编号、图片和模型配置路径后运行；没有附图时可省略 `-Files`，让 Agent 按任务需要抽帧。

```powershell
./scripts/run-agent.ps1 -PromptFile "outputs/<task-id>/task-brief.md" -ModelConfig "C:\path\to\opencode.json" -Files @("outputs/<task-id>/tmp/overview.jpg")
```

成片、剪辑清单和验证结果保存在 `outputs/<task-id>/`；完成情况、失败原因和下一步记在该目录的 `execution-notes.md`。修改成片时递增版本号，保留已有文件。

我如何约束 AI 的开发和执行，见 [AGENTS.md](AGENTS.md)。
