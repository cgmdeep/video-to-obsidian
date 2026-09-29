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
- [x] 提供仅包含允许字段的 `support-report --json`，不输出本机路径、供应商身份、Key、Cookie、Bearer 或签名 URL；
- [x] 安装、修复、卸载均返回稳定操作标识与错误码；
- [x] Windows ACL 实机与 GitHub Windows Runner 验证。

自动化合同：参数错误返回 `64`，首次安装失败返回 `20`，修复失败返回 `21`，卸载失败返回 `30`；JSON 同时提供 `operation`、`status` 和稳定 `error_code`。

### P3：Windows 图形向导

- [x] .NET 8 WPF 安装与连接向导，并由 Windows CI 编译；
- [x] 将当前 Python wheel 内嵌进自包含的 Windows x64 单文件 EXE；
- [x] 通过 winget 安装或检查 Python、Obsidian、Firefox 和 ffmpeg；
- [x] 提供 ZCode 官方下载页和 Bot Channel 官方教程入口；
- [x] 检测到已安装 ZCode 时直接打开，并可用专用工作区路径启动；未安装时才跳转官方说明；
- [x] 默认创建 `文档\视知库` Vault；
- [x] 提供隔离 Firefox 抖音/B站登录按钮、微信扫码引导和免费体检；
- [x] 英文干净 Windows Runner 可通过同一准备逻辑创建中文 Vault、专用工作区和 Firefox Profile；
- [x] 后台命令统一 UTF-8，外部安装步骤有超时并持续输出脱敏阶段进度；
- [x] 高级折叠区显示实验性逐字稿增强版；默认标准版不启动 ASR，切换只改受管档位字段并保留现有笔记与检查点。
- [x] ROG 候选安装器完成 `standard → transcript → standard` 零付费往返，生产配置未改写、Windows CRLF 与配置内容可字节级还原；未配置 ASR 时只提示非必需项不可用。
- [x] ROG 候选安装器完成脱敏支持报告实机验收；报告不含用户名、本机路径或认证材料，全程未调用付费模型。
- [x] 干净 Windows Runner 启动真实编译 EXE，验证 13 个必需动作和高级逐字稿选项；实际点击复制工作区路径和导出诊断报告，剪贴板、桌面 JSON、脱敏扫描与零付费标志全部通过。
- [x] 干净 Windows Runner 真实点击抖音/B站登录按钮，通过 Firefox 进程参数验证对应官方 URL 与隔离的 `VideoToObsidian` Profile；此项不代表用户已扫码。
- [x] 原视频归档等高风险选项不在当前图形向导开放；公开 Alpha 的高级区只提供实验性逐字稿档位。

### P4：干净机器和真实视频

- [x] 干净 Windows Runner 自动安装、原地修复、默认卸载、重装和受管私有目录卸载；
- [ ] 不含作者配置的 Windows 11 安装/修复/卸载；
- [x] 抖音小视频与 B站约 20 分钟典型视频各完成一次真实下载、K2.7 分析与入库；
- [x] B站 37 分钟长视频完成真实下载、完整时间线代理、K2.7 分析与入库；
- [x] 反讽与引用固定样本；
- [ ] 戏仿、夸张与反问扩展样本；
- [x] 自动固定集验证 Kimi 失败后人工重试复用下载及已完成逐字稿检查点；
- [x] 标准版真实视频闭环与 `standard → transcript → standard` 零付费档位切换；
- [ ] 逐字稿增强版真实视频全链路。

### P5：发布

- [x] CI 生成单文件 `VideoToObsidian.Setup.exe`；
- [x] 干净 Windows 验收后创建未签名 GitHub Pre-release（当前为 `v0.1.0-alpha.7`）；
- [x] 官网、README、安装指南与发行说明均明确 Alpha 未签名和 SmartScreen 风险；
- [x] 当前 Pre-release 同时提供 SHA256、SBOM、版本说明与卸载说明；
- [ ] 真实 usage 与费用拆分：ZCode 路由和视频分析分开记录。

## 安全规则

- 安装和体检不调用付费视频分析；
- 用户已有可用 ZCode 模型时不添加 Moonshot；
- 修改 ZCode 前必须备份，禁止覆盖无关供应商或 MCP；
- 日志、JSON 输出和 UI 不显示 Key、Cookie、Bearer 或签名媒体 URL；
- 含密钥的配置和恢复副本必须限制为当前用户可读。
