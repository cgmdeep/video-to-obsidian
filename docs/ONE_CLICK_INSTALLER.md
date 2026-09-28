# 一键安装器实施计划

## 产品边界

普通用户不需要 Codex、Coding Plan、Python、PowerShell 或 MCP 知识。唯一公开入口是
`VideoToObsidian.Setup.exe`。

用户只处理：

1. 选择或接受默认 Obsidian Vault；
2. 输入一次自己的 Kimi API Key；
3. 扫码登录抖音、B站和 ZCode 官方微信 Bot Channel。

ZCode 仍然需要一个可用模型通道，但 Coding Plan 不是必需条件：

- 已有 Coding Plan 或其他可用供应商：保留现状；
- 没有任何可用通道：用户明确选择后，复用同一 Kimi Key 添加 Moonshot；
- ZCode 只做文本路由和 MCP 调用，视频理解与正式笔记由 MCP 内部 Kimi 完成。

## 安装界面

安装器只保留五个可见步骤：

1. 欢迎与一键安装；
2. 自动安装进度；
3. Kimi Key 无回显输入与安全保存；
4. 抖音、B站、ZCode 微信三步扫码；
5. 免费体检、打开 Obsidian 与完成。

Python、ffmpeg、yt-dlp、MCP、配置文件和终端日志只出现在“遇到问题”高级面板。

## 专用 ZCode 工作区

安装器在用户文档目录创建 `视知库助手`，只写入受管的 `AGENTS.md`、`README.md`、
`.zcode/config.json` 和身份标记。它不修改用户的编程项目，也不在全局范围强制注入 MCP。

Bot Channel 必须在这个专用工作区中创建。

## 阶段与验收闸门

### P1：无 Coding Plan 的 ZCode 基础

- [x] 只读识别 ZCode 自定义模型供应商；
- [x] 不返回 API Key 或 Base URL；
- [x] 专用工作区和工作区级 MCP；
- [x] 明确操作后可增量配置 Moonshot；
- [x] Windows 实机上用 Moonshot 完成一次免费 `doctor` 工具调用；
- [x] 在专用工作区创建微信 Bot Channel，微信发“检查系统”可收到回复。

### P2：安装器后端合同

- [x] `doctor --json`；
- [x] `zcode-model-status --json`；
- [x] `bootstrap-workspace --json`；
- [x] `configure-zcode-moonshot --json`；
- [x] `set-kimi-key --stdin --json` 仅通过标准输入接收安装器密钥；
- [x] 统一 `onboarding-status --json`；
- [ ] 安装、修复、卸载均返回稳定错误码；
- [ ] Windows ACL 实机验证。

### P3：Windows 图形向导

- [x] .NET 8 WPF 安装与连接向导，并由 Windows CI 编译；
- [x] 将当前 Python wheel 内嵌进自包含的 Windows x64 单文件 EXE；
- [x] 通过 winget 安装或检查 Python、Obsidian、Firefox 和 ffmpeg；
- [x] 提供 ZCode 官方下载页和 Bot Channel 官方教程入口；
- [x] 默认创建 `文档\视知库` Vault；
- [x] 提供隔离 Firefox 抖音/B站登录按钮、微信扫码引导和免费体检；
- [x] 英文干净 Windows Runner 可通过同一准备逻辑创建中文 Vault、专用工作区和 Firefox Profile；
- [x] 后台命令统一 UTF-8，外部安装步骤有超时并持续输出脱敏阶段进度；
- [ ] 高级页才显示逐字稿、原视频归档和自定义目录。

### P4：干净机器和真实视频

- [ ] 不含作者配置的 Windows 11 安装/修复/卸载；
- [ ] 抖音、B站短视频各一条；
- [ ] 20～30 分钟长视频；
- [ ] 反讽/引用/戏仿样本；
- [ ] Kimi 失败后复用检查点；
- [ ] 标准版与逐字稿增强版。

### P5：发布

- [x] CI 生成单文件 `VideoToObsidian.Setup.exe`；
- [ ] 干净 Windows 验收后创建未签名 GitHub Pre-release；
- [ ] 代码签名或明确的 Alpha 未签名风险提示；
- [ ] SHA256、SBOM、版本说明与卸载说明；
- [ ] 真实 usage 与费用拆分：ZCode 路由和视频分析分开记录。

## 安全规则

- 安装和体检不调用付费视频分析；
- 用户已有可用 ZCode 模型时不添加 Moonshot；
- 修改 ZCode 前必须备份，禁止覆盖无关供应商或 MCP；
- 日志、JSON 输出和 UI 不显示 Key、Cookie、Bearer 或签名媒体 URL；
- 含密钥的配置和恢复副本必须限制为当前用户可读。
