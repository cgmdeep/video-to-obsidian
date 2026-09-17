# Windows 安装与扫码指南

本指南面向普通使用者。推荐把仓库地址交给可信的 AI 助手，让它先阅读根目录 `AGENTS.md` 再操作；用户本人只处理账号、扫码、API Key 和付费确认。

## 安装前准备

- Windows 11；
- Python 3.11 或 3.12；
- ZCode；
- 至少 5 GB 可用空间，处理长视频时建议更多；
- 用户自己的 Kimi、抖音和B站账号；
- 一个已有或准备新建的 Obsidian Vault。

不要把 API Key、Cookie、验证码或微信登录信息发给 AI 助手。API Key 应在无回显终端中由用户亲自输入。

## 1. 安装程序

在仓库根目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 `
  -VaultPath "D:\Video Knowledge Base" `
  -Profile standard `
  -InstallApps
```

`-InstallApps` 只通过 Windows `winget` 安装 Firefox、Obsidian 和 ffmpeg。yt-dlp 会安装在项目自己的 Python 虚拟环境中。已有软件会由 winget 检查或更新，不会安装浏览器扩展和 Obsidian 社区插件。

标准版不需要本地显卡和 SenseVoice。只有明确需要原始逐字稿时才把 `-Profile standard` 改为 `-Profile transcript`；增强版还需要单独部署或连接 SenseVoice 服务。

## 2. 输入 Kimi API Key

安装脚本结束后，在同一仓库运行：

```powershell
.\.venv\Scripts\video-to-obsidian.exe set-kimi-key
```

终端会要求输入两次且不回显，Key 保存到 Windows 凭据库。不要把 Key 写进 `config.toml`、ZCode 配置、`.env`、聊天消息或截图。

## 3. 扫码登录视频平台

打开 Firefox 的 Profile 管理器：

```powershell
& "$env:PROGRAMFILES\Mozilla Firefox\firefox.exe" -P
```

选择安装器创建的 `VideoToObsidian` Profile，再分别打开抖音和B站官网，用用户自己的账号扫码登录。不要导入日常浏览器 Profile，也不要使用网上共享 Cookie。

扫码完成后可以关闭 Firefox。以后 Cookie 失效或平台要求重新验证时，再用同一个 Profile 扫码。

## 4. 打开 Obsidian Vault

启动 Obsidian，选择“打开本地仓库”，选择安装命令中传入的 `VaultPath`。程序不会修改现有 `.obsidian`、主题或插件。

Obsidian 不需要一直运行；MCP 可以在应用关闭时写入 Markdown。

## 5. 连接 ZCode 和微信

安装器只会在 ZCode 配置中增加名为 `video-to-obsidian` 的本地 stdio MCP，并在修改前创建恢复副本。它不会安装个人微信 Hook、注入器或非官方机器人。

1. 使用 ZCode 官方入口连接自己的微信；
2. 按 ZCode 界面提示由用户本人扫码；
3. 重启 ZCode，让新的本地 MCP 生效；
4. 在 ZCode 中先让 AI 助手调用 `doctor`，确认所有必需检查通过；
5. 先调用免费的 `route_video` 检查平台路由，再由用户确认是否进行会产生 Kimi 费用的真实分析。

若目标 ZCode 版本的配置结构与当前仓库不同，AI 助手必须停止，不得猜测字段或覆盖其他 MCP。

## 6. 日常使用

把完整抖音或B站分享文本发给 ZCode。默认使用 K2.7、无逐字稿、不永久保存原视频。只有消息中出现精确短语“使用K3深度分析”才启用 K3。

长期总结偏好可以直接告诉 AI 助手，例如“以后按时间线详细总结，保留数字和反讽语境”。单条视频的要求和链接写在同一条消息中即可。

## 7. 体积、费用与失败恢复

- 现有样本中，5～46 分钟的视频约 34.7～306.9 MB；不同画质差异很大；
- 普通 Markdown 通常约 4～14 KB，带逐字稿通常约 14.7～63.1 KB；
- 建议临时空间至少为预计视频大小的 3 倍再加 1 GB；
- Kimi 按 token 计费，不按视频条数或分钟固定计价；
- 每个工具调用最多进行一次 Kimi 分析；失败不会在服务内部盲目重试；
- Kimi 失败时会保留下载、代理和逐字稿检查点，人工重试可复用；
- 成功且未选择保存视频时会清理视频和代理。

价格以 [Kimi 官方页面](https://platform.kimi.com/docs/pricing/chat) 为准。真实测试必须记录 API 返回的 `usage` 和账户扣费，不能只根据视频时长估算。

## 8. 诊断和卸载

免费诊断：

```powershell
.\.venv\Scripts\video-to-obsidian.exe doctor --json
```

安全卸载：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
```

这会移除本项目的 ZCode MCP 条目和 `.venv`，但保留 Vault、Firefox Profile、第三方软件和私有运行数据。只有确认不再需要检查点、候选笔记和视频归档时，才显式添加 `-RemovePrivateData`。

