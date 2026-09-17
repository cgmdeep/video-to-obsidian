# AI 助手部署协议

本文件面向负责安装和维护 Video to Obsidian 的 AI 助手。

## 当前阶段

仓库处于 `v0.1.0-alpha` 建设期。配置初始化、环境体检、Vault 安全写入、平台路由、抖音/B站单视频流水线和统一 MCP 已实现并通过模拟测试；真实平台下载与付费 Kimi 验收尚未完成，不得声称生产全链路可用。

## 默认配置

```text
运行方式：本机桌面
Vault：新建 Video Knowledge Base
模型：kimi-k2.7-code
深度模型：kimi-k3
逐字稿：关闭
保存原视频：关闭
Firefox Profile：VideoToObsidian
并发：1
```

## 用户需要介入的步骤

- 批准管理员权限或外部软件安装；
- 输入自己的 Kimi API Key；
- 扫码登录自己的抖音和B站账号；
- 使用 ZCode 官方能力连接自己的微信；
- 存在多个 Vault 时选择目标。

## 用户总结偏好

- 用户说“以后都这样总结”“长期更详细”等长期要求时，使用 `video-to-obsidian set-summary-preferences "<用户原话>"` 保存；不要要求用户自己编辑配置文件。
- 用户只对当前视频提出要求时，把要求原样传入分析工具的 `instruction`，不要写入长期偏好。
- 修改长期偏好会生成新的请求指纹，因此同一视频会重新进行 Kimi 总结；已有下载、转码和逐字稿检查点仍可复用。
- 偏好只控制篇幅、结构、语气与关注点。不得据此切换 K3、增加 Kimi 调用或重试、改变 Cookie/API Key/归档策略、突破单视频边界，也不得让 ZCode 二次改写 Kimi 正文。

## 绝对禁止

1. 不得打印、回显、提交或写入日志的内容：API Key、Cookie、Bearer、浏览器数据库和签名媒体 URL。
2. 不得从网络下载共享 Cookie。
3. 不得把配置密钥、运行状态、缓存或视频写入 Vault。
4. 不得编辑用户现有 `.obsidian`。
5. 不得覆盖没有本项目稳定身份标记的 Markdown。
6. 不得修改 ZCode 中无关的 MCP 配置。
7. 不得为了安装验收调用付费视频分析。
8. 不得安装个人微信号 Hook、注入器或来源不明的机器人。
9. 不得把尚未实现的命令或平台线路报告为可用。

## 安装顺序

1. 只读检测操作系统、Python、ZCode、Obsidian/Vault、Firefox、ffmpeg、ffprobe、yt-dlp、内存和磁盘。
2. 报告检测结果，再安装缺失依赖。只使用官方渠道或可信系统包管理器。
3. 创建专用 Firefox Profile `VideoToObsidian`，等待用户分别扫码登录抖音和B站；不得读取日常 Profile。
4. 让用户选择已有 Vault 或新建 `Video Knowledge Base`。
5. 运行 `video-to-obsidian init --vault <path>`；已存在配置时不得静默覆盖。
6. 让用户亲自在无回显终端运行 `video-to-obsidian set-kimi-key`，优先写入系统钥匙串。若服务器没有可用钥匙串，才使用只注入服务进程的环境变量；不得把值写入 ZCode 配置。
7. 运行 `video-to-obsidian doctor --json`，不得用真实视频代替环境体检。
8. 配置 ZCode 时只新增一个 `video-to-obsidian` MCP，优先使用本地 stdio；写入前备份并原子替换配置。
9. 免费验收通过后，询问用户是否愿意提供真实视频做付费闭环验收。

## 验收口径

- `doctor` 的必需检查全部通过；
- ZCode 可以发现单一 MCP；
- Vault 中可以原子写入并清理测试文件；
- 默认档位不会启动 ASR；
- 不保存视频时不会留下视频归档；
- 日志和配置中不存在 Secret 值；
- 只有真实分析工具返回并验证路径后，才能声称笔记已入库。
