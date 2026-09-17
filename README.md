# Video to Obsidian

把抖音或哔哩哔哩单视频交给 Kimi 分析，并把正式中文笔记写入 Obsidian。

推荐入口是：

```text
用户自己的微信 → 用户自己的 ZCode → video-to-obsidian MCP → Obsidian
```

也可以直接把完整分享文本粘贴到 ZCode。

> 当前状态：`v0.1.0-alpha` 建设中，尚未发布。当前仓库只完成公共配置、环境体检、安全写入和视频路由骨架；真实抖音/B站下载与 Kimi 分析尚未迁入，不得把它描述为已经完成全链路。

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
video-to-obsidian doctor
video-to-obsidian route "完整的视频分享文本"
video-to-obsidian mcp
```

`init` 会建立公共配置和 `Douyin/`、`Bilibili/` 两个笔记目录，但不会修改 `.obsidian`。

`doctor` 只检查配置、Vault、Kimi Key 是否存在，以及 Firefox、ffmpeg、ffprobe、yt-dlp、Obsidian 是否可用；不会显示密钥值，也不会发起付费视频分析。

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
- API Key 优先保存在系统钥匙串；当前 alpha 只读取进程环境变量 `KIMI_API_KEY`。
- 不把密钥、Cookie、Authorization、签名视频地址写入笔记或日志。
- 不修改用户现有 `.obsidian` 配置、主题和插件。

AI 助手部署要求见 [AGENTS.md](AGENTS.md)。

