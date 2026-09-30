# Windows 安装与扫码指南

本指南面向普通使用者。目标流程是双击一个安装器，用户本人只处理账号、扫码、API Key 和真实视频分析前的付费确认。仓库命令只放在文末的高级恢复部分。

维护者或首批体验用户需要形成正式验收证据时，使用[陌生用户首次使用验收](FRESH_USER_ACCEPTANCE.md)；日常用户无需执行其中的记录步骤。

## 安装前准备

- Windows 11；
- 至少 5 GB 可用空间，处理长视频时建议更多；
- 用户自己的 Kimi、抖音和B站账号；
- 能接收 ZCode 官方微信 Bot Channel 消息的个人微信。

Python、Firefox、Obsidian 和 ffmpeg 可以由安装器通过 `winget` 补齐。ZCode 仍需按其官方页面安装。不要把 API Key、Cookie、验证码或微信登录信息发给 AI 助手；只在安装器的密钥框或官方扫码页面中亲自输入。

## 1. 运行安装器

下载正式 Release 中的 `VideoToObsidian.Setup.exe`，核对发布页 SHA256 后双击运行。当前 Alpha 未签名，Windows SmartScreen 可能提示风险；正式 Release 出现前，不要从群聊、网盘或第三方网站下载安装包。

点击“安装 / 修复本机”，接受默认路径或选择新的 Obsidian Vault。安装器会使用官方 `winget` 来源补齐依赖，并把自身核心放在 `%LOCALAPPDATA%\VideoToObsidian\runtime`。重复点击会执行幂等修复，不会覆盖无关 ZCode 配置。默认标准版不需要显卡、NAS、Tailscale 或 SenseVoice。

普通用户保持“高级设置”折叠并使用标准版即可。如果你已经在本机运行兼容的 SenseVoice 服务，可以展开高级设置并勾选“逐字稿增强版”；默认连接 `127.0.0.1:8010`。增强服务不可用时会跳过逐字稿而不阻止 Kimi 正式笔记。切换档位后再次点击“安装 / 修复本机”，安装器只改受管档位字段，保留 Vault、偏好、缓存、检查点和未知的未来配置项。当前 Alpha 不负责安装 SenseVoice，也不把作者的远程服务提供给公众。

## 2. 输入 Kimi API Key

在“连接 Kimi”中输入自己的 Kimi API Key，点击“安全保存并自动补齐”。Key 保存到 Windows 凭据库，界面和日志不会显示其值。不要把 Key 写进聊天消息、截图或普通文本文件。

## 3. 扫码登录视频平台

点击安装器中的“登录抖音”和“登录B站”。两个按钮会打开安装器创建的 `VideoToObsidian` Firefox Profile。用自己的账号扫码，不要导入日常浏览器 Profile，也不要使用网上共享 Cookie。

扫码完成后可以关闭 Firefox。以后 Cookie 失效或平台要求重新验证时，再用同一个 Profile 扫码。

## 4. 打开 Obsidian Vault

点击“用 Obsidian 打开”，或启动 Obsidian 后选择安装器中显示的 Vault。程序不会修改用户已有 `.obsidian`、主题或插件，也不要求安装社区插件。

Obsidian 不需要一直运行；MCP 可以在应用关闭时写入 Markdown。

## 5. 连接 ZCode 和微信

安装器会新建 `文档\视知库助手`，其中只有本工作区的路由规则和 `video-to-obsidian` 本地 MCP。它不会接入企业微信，也不会安装个人微信 Hook、注入器或非官方机器人。

1. 点击“安装 / 打开 ZCode”，完成 ZCode 官方安装和首次启动；
2. 点击“复制工作区路径”，在 ZCode 的“打开工作区”中选择这个目录；
3. 打开 ZCode 左下角“移动端远程控制”，在右侧 Bot Channel 选择“微信”；
4. 按 ZCode 官方界面由用户本人扫码并确认；
5. 回到安装器点击“重新检查”，再在微信发送“检查系统”；
6. 免费检查通过后，再发送真实视频链接。

微信 Bot Channel 是 ZCode 官方能力，操作的是电脑上已打开的工作区；因此电脑和 ZCode 需要保持运行。没有 Coding Plan 时，可以使用自己的 Kimi/Moonshot API 通道。安装器优先保留已有模型配置，不会覆盖其他供应商。

需要求助时，点击“导出脱敏诊断报告”，把桌面的 `视知库诊断报告.json` 发给维护者。报告只包含安装检查状态，不包含本机路径、API Key、Cookie、Bearer 或签名媒体地址，也不会调用付费模型。

若目标 ZCode 版本的配置结构与当前仓库不同，AI 助手必须停止，不得猜测字段或覆盖其他 MCP。

## 6. 日常使用

把完整抖音或B站分享文本发给 ZCode。默认使用 K2.7、无逐字稿、不永久保存原视频。只有消息中出现精确短语“使用K3深度分析”才启用 K3。

长期总结偏好可以直接告诉 AI 助手，例如“以后按时间线详细总结，保留数字和反讽语境”。单条视频的要求和链接写在同一条消息中即可。

## 7. 体积、费用与失败恢复

- 现有样本中，5～46 分钟的视频约 34.7～306.9 MB；不同画质差异很大；
- 普通 Markdown 通常约 4～14 KB，带逐字稿通常约 14.7～63.1 KB；
- 建议临时空间至少为预计视频大小的 3 倍再加 1 GB；
- Kimi 按 token 计费，不按视频条数或分钟固定计价；
- 工具返回的 `video_analysis_usage` 只统计视频分析，兼容字段 `usage` 与它相同；
- ZCode 路由模型发生在 MCP 工具之外，`zcode_routing_usage.available=false` 时应到 ZCode 或相应模型供应商查看，不能和视频分析费用混算或假定为零；
- 每个工具调用最多进行一次 Kimi 分析；失败不会在服务内部盲目重试；
- Kimi 失败时会保留下载、代理和逐字稿检查点，人工重试可复用；
- 成功且未选择保存视频时会清理视频和代理。

价格以 [Kimi 官方页面](https://platform.kimi.com/docs/pricing/chat) 为准。真实测试必须分别记录视频分析 API 返回的 usage 与 ZCode 路由侧 usage/账单；拿不到路由侧数据时明确写“不可用”，不能只根据视频时长估算。

## 8. 诊断和卸载

普通用户优先看安装器底部“免费检查”。不再使用时，点击“安全卸载（保留笔记）”；默认只移除视知库核心和受管 MCP，保留 Vault、专用工作区、Firefox Profile、Kimi Key、检查点和第三方软件。

若安装完成后 Obsidian 没有显示仓库、ZCode 没有显示专用工作区，或右侧没有“知识激活”，
不要重复新建目录。先关闭 Obsidian 和 ZCode，再用当前安装器执行“安装 / 修复本机”。仍未恢复时，
按 [Windows 手动恢复与 Agent 兜底](RECOVERY_WINDOWS.md) 手动打开，或把其中的受限任务文本交给本机 Agent。

以下命令只供开发者、AI 助手或故障恢复使用，需要先获取源码：

免费诊断：

```powershell
& "$env:LOCALAPPDATA\VideoToObsidian\runtime\Scripts\video-to-obsidian.exe" doctor --json
```

安全卸载：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
```

这会移除本项目的 ZCode MCP 条目、安装器核心和源码虚拟环境，但保留 Vault、专用工作区、Firefox Profile、第三方软件和私有运行数据。只有确认不再需要 Kimi Key、检查点、候选笔记和视频归档时，才显式添加 `-RemovePrivateData`。
