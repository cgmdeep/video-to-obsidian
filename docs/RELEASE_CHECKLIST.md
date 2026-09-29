# v0.1.0 Alpha 发布门槛

`v0.1.0-alpha.3` 是未签名 GitHub Pre-release，不是稳定版。发布流水线必须从标签重新测试、构建，在干净 Windows Runner 运行免费安装与卸载生命周期验收，并同时生成 SHA256 与 SBOM。真实付费样本、图形交互验收和规模稳定性中的未完成项必须继续作为 Release 已知限制公开，不得写成已通过。

## 已完成

- 干净独立 Git 历史，不继承私人生产仓库提交；
- 跨平台公共配置目录；
- Obsidian 人类可检索文件名与稳定来源身份；
- 抖音/B站普通单视频适配器；
- B站多P必须显式选择；
- Kimi 每个工具调用最多一次，保留长超时与16K输出预算；
- Kimi usage、结束原因、正文/推理长度诊断，不保存思考正文；
- 默认不调用ASR、不保存原视频；
- 可选 SenseVoice 兼容接口；
- 下载源、逐字稿和完整时间线代理检查点；
- 单一 stdio MCP；
- ZCode 配置备份、幂等更新和局部卸载；
- 无费用模拟测试；
- 当前文件树私有路径与常见 Secret 模式扫描无命中。
- Apache-2.0 开源许可证和包元数据；
- Windows/Linux、Python 3.11/3.12 CI 与可安装 wheel 构建；
- Windows x64 自包含单文件安装向导由 CI 构建，普通用户无需预装 .NET；
- 每周依赖漏洞审计、完整 Git 历史 Gitleaks 扫描和 Dependabot；
- 私密漏洞报告说明与 GitHub Private Vulnerability Reporting；
- Windows 可选 winget 依赖安装、专用 Firefox Profile 检查和安全卸载脚本；
- 干净 Windows Runner 自动安装、原地修复、默认卸载、重装与受管私有目录卸载；
- 人类安装扫码指南与可复现公开验收记录模板。

## 公开前必须完成

- [x] 加入 Apache License 2.0，并在 Python 包元数据中声明。
- [x] 使用一台不含作者私人配置的 Windows 11 普通账户跑图形安装准备流程。
- [x] 记录干净 Runner 安装器的 commit、字节数、SHA256 和 CI 链接。
- [x] 核验目标 ZCode 版本的 stdio MCP 配置字段。
- [x] 在 Windows 实机 ZCode 中，用用户自有 Moonshot Key 调用免费 `doctor`。
- [x] 微信 Bot Channel 绑定到专用“视知库助手”工作区，不影响其他 ZCode 项目。
- [x] 验证 Firefox 专用 Profile 名称能被下载适配器正确读取。
- [x] 用一条小型抖音和一条 B站长视频完成真实下载；B站短视频仍待固定样本验证。
- [x] 经用户明确同意后，分别完成一次真实 K2.7 付费分析。
- [ ] 验证无逐字稿标准版和远程 SenseVoice 增强版。
- [ ] 验证Kimi失败后复用检查点，不重复下载。
- [ ] 验证笔记、缓存、state、candidate和archive物理隔离。
- [x] CI 使用 Gitleaks 扫描完整 Git 历史，并使用 pip-audit 审计依赖。
- [x] 仓库已切换为 Public，GitHub Private Vulnerability Reporting API 报告 `enabled: true`，公开 Security Policy 页面可访问。
- [ ] 完成真实付费样本后，在验收记录中填写 usage、当日单价与实际扣费；README 不写死每条价格。
- [ ] 核验 README 中模型名称、充值规则和外部安装说明在发布当天仍有效。
- [ ] 标签构建生成版本化 EXE、`SHA256SUMS`、SPDX SBOM、发行说明和干净 Runner 报告。

### 2026-09-27 干净 Windows Runner 证据

- commit：`9b0a4206608a34c1210444f675e1d0566fb91127`；
- 工作流：[Windows clean acceptance #36308011099](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36308011099)；
- `VideoToObsidian.Setup.exe`：71,663,006 字节；
- SHA256：`e9f8eda8f8bf35b764ed1936ec791f4dc02772192eb850fcbe0cac44409692f6`；
- 结果：临时英文 Windows Runner 完成核心、Firefox、Obsidian、ffmpeg、默认中文 Vault 和专用 ZCode 工作区准备；确认专用 Firefox Profile、单一 MCP、无 `.obsidian`、脱敏配置和免费 `doctor`；`contains_secrets=false`、`paid_call_performed=false`；
- 边界：这是无人值守准备验收，不替代 Windows 11 图形点击、用户扫码、ZCode 微信 Bot、卸载和真实视频验收。

### 2026-09-29 干净 Windows 生命周期证据

- commit：`c30926fc34c72e370b2bb6a070ecf9ea646d05fc`；
- 工作流：[Windows clean acceptance #36503042863](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36503042863)；
- `VideoToObsidian.Setup.exe`：71,678,488 字节；
- SHA256：`c51446235f997c0f8c8e98c49fcda70f2a916fbf7582d4ec01862aec9a6dc0e0`；
- 结果：首次安装、原地修复、默认安全卸载、重装与私有数据卸载均通过；Vault、专用工作区、Firefox Profile 和无关 MCP 在应保留的阶段均保留；全程无 Secret 输出且无付费调用。

### 2026-09-29 alpha.2 候选阻断记录

- 标签 `v0.1.0-alpha.2` 的发布流水线在 Firefox 准备阶段被闸门阻断，没有生成 GitHub Release；
- 原因是干净 Windows Runner 的 `winget` 源临时返回 `No package found matching input criteria`；
- `alpha.3` 增加 `winget` 源刷新、受控重试和 Mozilla 官方下载降级后重新执行完整发布验收；
- 官网不得引用 `alpha.2` 标签或失败流水线中的临时构建物。

## 不进入 v0.1

- 项目方托管的公共微信机器人（用户自己连接的 ZCode 官方 Bot Channel 属于 v0.1 主流程）；
- 支付、余额、订单和退款；
- 多P批量、合集、直播、番剧与互动视频；
- 公共 Cookie；
- 自动绕过会员、地区限制或 DRM；
- 默认永久保存原视频；
- 自动安装 Obsidian 社区插件；
- 面向公网暴露未经鉴权的 MCP。
