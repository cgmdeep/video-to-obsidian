# douyin&bilibili Video to Obsidian

把抖音或哔哩哔哩单视频交给 Kimi 分析，并把正式中文笔记写入 Obsidian。

推荐入口是：

```text
用户自己的微信 → 用户自己的 ZCode → video-to-obsidian MCP → Obsidian
```

也可以直接把完整分享文本粘贴到 ZCode。

> 当前状态：`v0.1.0-alpha` 建设中，尚未发布。抖音/B站单视频下载、Kimi一次分析、可选逐字稿、检查点和 Obsidian 入库代码已经接通并通过无费用模拟测试；尚未完成独立设备上的真实平台下载与付费 Kimi 验收，不得描述为生产可用。

## 设计目标

- 使用用户自己的 Kimi API Key、抖音账号和B站账号。
- 默认 Kimi K2.7；只有精确短语“使用K3深度分析”触发 K3。
- 默认不生成逐字稿、不永久保存原视频。
- 可选连接 SenseVoice，生成原始逐字稿。
- 视频、Cookie、密钥、缓存和运行状态不进入 Obsidian Vault。
- 首版一次只处理一条视频，失败不盲目重试。
- 人类只负责 API Key、扫码和 Vault 选择，其余部署工作交给 AI 助手。

## 当前可用命令

```bash
video-to-obsidian init --vault "/path/to/Video Knowledge Base"
video-to-obsidian set-kimi-key
video-to-obsidian doctor
video-to-obsidian route "完整的视频分享文本"
video-to-obsidian mcp
video-to-obsidian configure-zcode
```

`init` 会建立公共配置和 `Douyin/`、`Bilibili/` 两个笔记目录，但不会修改 `.obsidian`。

`set-kimi-key` 会在终端无回显地读取两次 Key，并保存到 Windows 凭据库或 macOS 钥匙串。无钥匙串的服务器可以显式向服务进程注入 `KIMI_API_KEY`。

`doctor` 只检查配置、Vault、Kimi Key 是否存在，以及 Firefox、ffmpeg、ffprobe、yt-dlp、Obsidian 是否可用；只显示Key来源，不显示密钥值，也不会发起付费视频分析。

统一 MCP 当前暴露：

- `doctor`：免费环境体检；
- `route_video`：免费识别平台和 K3 触发词；
- `analyze_douyin`：抖音普通单视频；
- `analyze_bilibili`：B站普通单视频，多P必须使用带 `?p=` 的具体链接。

两个分析工具默认 `save_video=false`，每次工具调用最多发起一次 Kimi 分析，不在服务内部自动重试。

## 总结不合口味怎么办

总结强度和写法不是固定死的。直接告诉 AI 助手你的偏好即可，例如：

```text
以后总结更详细，按时间线展开，所有数据和例子都保留，特别注意区分反讽和作者真实观点。

以后少写背景铺垫，重点提炼方法、操作步骤、参数和失败原因。
```

AI 助手会把长期偏好保存到 Vault 外的私有配置文件：

```bash
video-to-obsidian set-summary-preferences "按时间线详细总结，保留数据、例子和反讽语境"
```

查看偏好或恢复默认：

```bash
video-to-obsidian show-summary-preferences
video-to-obsidian clear-summary-preferences
```

只想调整某一条视频时，把要求和链接写在同一条消息中即可，不会改变长期偏好。偏好可以调整篇幅、结构、语气和关注点，但不会自动切换 K3、增加重试、改变是否保存视频，也不能绕过单视频、隐私和安全边界。

## Windows alpha 安装

仓库克隆完成后，由 AI 助手在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 `
  -VaultPath "D:\Video Knowledge Base" `
  -Profile standard
```

脚本只建立隔离 Python 环境、安装本项目、初始化 Vault 配置并在找到 ZCode 配置时增加单一 MCP。它不会静默安装 Obsidian、Firefox、ffmpeg 或 yt-dlp，不会保存 Kimi API Key，也不会替用户完成扫码。

当前 alpha 首发以 Windows 11 为优先验证平台。发布门槛见 [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md)。

## 两种档位

### 标准版（默认）

- Kimi 直接观看视频并写正式笔记。
- 不运行本地 SenseVoice。
- 不需要显卡或闲置服务器。
- 默认不保存原视频。

### 逐字稿增强版

- 增加 SenseVoice 原始逐字稿。
- SenseVoice 可以在本机运行，也可以连接远程闲置主机。
- 逐字稿失败不应阻止 Kimi 正式笔记入库。

## 日常需要运行什么

| 软件或服务 | 是否需要保持运行 | 说明 |
|---|---|---|
| ZCode | 是 | 对话和微信入口。 |
| Video to Obsidian MCP | 是 | 由 ZCode 自动启动，无单独窗口。 |
| Obsidian | 否 | Markdown 可以在应用关闭时写入。 |
| Firefox | 否 | 只在首次扫码或 Cookie 失效时打开。 |
| SenseVoice | 仅增强版 | 标准版不需要。 |
| ffmpeg / yt-dlp | 无需手工打开 | 由流水线调用。 |

## 文件体积参考

现有真实 B站样本中，约 5～46 分钟的视频下载体积约 34.7～306.9 MB；带逐字稿的 Markdown 约 14.7～63.1 KB，去掉逐字稿后约 4～14 KB。视频清晰度越高，下载和临时空间通常越大。

不保存原视频时，成功后应删除下载视频、Kimi 临时代理和临时音频，最终通常只留下几 KB 到几十 KB 的 Markdown。

## 安全边界

- Cookie 只能来自用户自己的账号。
- 不提供共享 Cookie，不绕过会员、付费内容或 DRM。
- API Key 优先保存在系统钥匙串；无可用钥匙串的服务器才使用进程环境变量 `KIMI_API_KEY`。
- 不把密钥、Cookie、Authorization、签名视频地址写入笔记或日志。
- 不修改用户现有 `.obsidian` 配置、主题和插件。

AI 助手部署要求见 [AGENTS.md](AGENTS.md)。
