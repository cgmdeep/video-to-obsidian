# v0.1.0 Alpha 发布门槛

`v0.1.0-alpha.7` 是未签名 GitHub Pre-release，不是稳定版。发布流水线必须从标签重新测试、构建，在干净 Windows Runner 运行免费安装与卸载生命周期验收，并同时生成 SHA256 与 SBOM。真实付费样本、图形交互验收和规模稳定性中的未完成项必须继续作为 Release 已知限制公开，不得写成已通过。

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
- [x] 用一条小型抖音、一条约 20 分钟的 B站典型视频和一条 B站长视频完成真实下载。
- [x] 经用户明确同意后，分别完成一次真实 K2.7 付费分析。
- [x] 验证无逐字稿标准版：抖音与 B站真实样本均关闭逐字稿并成功入库。
- [ ] 验证远程 SenseVoice 增强版。
- [x] 自动固定集验证 Kimi 失败后人工重试复用下载检查点，不重复下载；真实服务中断仍待抽样。
- [x] 自动固定集验证笔记、缓存、state、candidate和archive物理隔离。
- [x] CI 使用 Gitleaks 扫描完整 Git 历史，并使用 pip-audit 审计依赖。
- [x] 仓库已切换为 Public，GitHub Private Vulnerability Reporting API 报告 `enabled: true`，公开 Security Policy 页面可访问。
- [x] 完成真实付费样本后，在验收记录中填写 usage、当日官方单价与费用估算；README 不写死每条价格，也不把估算冒充账单实扣值。
- [x] 2026-09-29 按 Kimi 与 ZCode 官方文档核验 README 中模型名称、K3 充值门槛、官方价格入口、ZCode 安装与 Bot Channel 入口仍有效。
- [x] `v0.1.0-alpha.7` 标签构建生成版本化 EXE、`SHA256SUMS`、SPDX SBOM、发行说明和干净 Runner 报告。

### 2026-09-29 本地一致性与失败恢复固定集

- 当前全部 122 项核心测试通过；其中包含 100 个无付费并发提交的单节点排队固定集、30 轮确定性上游故障恢复巡检、总结质量提示词合同、Windows ACL 原生集成检查和最新失败边界回归；
- 旧版 Vault 根目录与新版平台子目录统一按稳定身份检查，同一来源不会再静默生成第二份正式笔记；
- Vault 中只有用户笔记，cache、state、candidate 和 archive 均在私有运行目录；
- Kimi 连接失败会保留下载检查点，人工重试不再次下载；
- 已完成的逐字稿在后续 Kimi 失败重试时不会重复转写；ASR 必需模式失败会在 Kimi 前停止并保留来源检查点；
- 已有正式笔记但状态丢失时，在任何下载和 Kimi 调用前返回冲突，避免“付费后才发现不能覆盖”；
- 用户修改总结偏好或明确启用 K3 时，新结果只保存为 Vault 外候选稿，原正式笔记不变；
- 本节是无费用自动固定集，不替代真实平台登录失效、网络中断和付费模型异常抽样。

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

### 2026-09-29 源码卸载补充证据

- commit：`ee58e82f6bf9b1b8ec80db8e31a25d683b76ce9e`；
- 工作流：[Windows clean acceptance #36537411556](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36537411556)；
- 结果：仓库 `scripts/uninstall.ps1` 在干净 Windows 上先移除安装核心和受管 MCP，同时保留 Vault、工作区、Firefox Profile 与无关 MCP；随后重装、修复、安装器默认卸载、重装和私有数据卸载全部通过；
- 本轮还验证英文 Windows 旧控制台编码边界，子 Python 命令使用临时 UTF-8 环境且执行后恢复；六份报告均不含 Secret 且未触发付费调用。

### 2026-09-29 最新安装器支持工作流证据

- commit `129ca2a2d473bd5011b1bd7196bfc724cba4e486`；CI [`#36585588795`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36585588795) 与 Security [`#36585589160`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36585589160) 通过；
- ROG 候选包 SHA256 为 `12a50f18ad9efff1294981f409fb411038bf00c7a2c1880650f12e59c984c732`，内置载荷校验与原地修复均通过，复用现有 Vault 和专用工作区，未调用付费模型；
- `support-report` 在实机只返回允许字段，对用户名、本机路径、Key/Cookie/Bearer/签名 URL 扫描无命中；
- 安装器可检测 ROG 上的已安装 ZCode，直接打开应用或传入专用工作区；仅在未安装时跳转官方安装说明。

### 2026-09-29 alpha.6 正式发布证据

- 标签提交：`79b3636a00f60bc77ae8338f085886439336ef3a`；
- Release workflow：[`#36587899899`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36587899899) 成功，111 项核心测试及干净 Windows 首次准备、修复、卸载、重装、私有目录清理生命周期全部通过；
- Security workflow：[`#36587313011`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36587313011) 成功；
- `VideoToObsidian.Setup.exe`：71,689,162 字节，SHA256 `fc8e3221a50c15b7709fde0d5f14e75127b8d5efa55f93d21c61358e0f3b74ab`；
- 同一 Pre-release 提供 `SHA256SUMS` 与 SPDX 2.3 SBOM；发布页：<https://github.com/cgmdeep/video-to-obsidian/releases/tag/v0.1.0-alpha.6>。

### 2026-09-30 alpha.7 正式发布证据

- 标签提交：`d07e63901ca92435a5b29089b792e9c062002c34`；
- Release workflow：[`#36597614427`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36597614427) 成功，121 项核心测试及干净 Windows 首次准备、修复、卸载和重装生命周期全部通过；
- 最终候选提交的 CI workflow [`#36597275259`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36597275259) 与 Security workflow [`#36597275469`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36597275469) 均成功；
- `VideoToObsidian.Setup.exe`：71,691,693 字节，SHA256 `b03b99201c01c49016fd92ecdc770ebbf0d2077750b7ba9795614cbb451e399e`；
- 本地重新下载全部发布资产后，`SHA256SUMS` 对 EXE、Python wheel/sdist、SPDX 2.3 SBOM 和干净 Runner 报告校验全部通过；发布页：<https://github.com/cgmdeep/video-to-obsidian/releases/tag/v0.1.0-alpha.7>。

### 2026-09-30 图形安装器动作证据

- commit `07d75cb27a442835a3d446e177631a240f5880f3`；[`Windows clean acceptance #36611285887`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36611285887)、[`CI #36611164527`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36611164527) 与 [`Security #36611164388`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36611164388) 成功；
- 真实编译后的 EXE 暴露 13 个必需动作和可展开的逐字稿增强选项；工作区路径复制动作在剪贴板上按完整路径校验；
- 诊断导出动作真实创建桌面 JSON 并上传证据；报告不含 Secret 或本机路径，不发起付费调用；
- 本轮同时继续通过首次准备、修复、默认卸载、重装、Windows Credential Manager 保留/删除和私有数据卸载；不替代真实平台扫码、ZCode 微信绑定或首条付费视频。

### 2026-09-29 alpha.2 候选阻断记录

- 标签 `v0.1.0-alpha.2` 的发布流水线在 Firefox 准备阶段被闸门阻断，没有生成 GitHub Release；
- 原因是干净 Windows Runner 的 `winget` 源临时返回 `No package found matching input criteria`；
- `alpha.3` 增加 `winget` 源刷新、受控重试和 Mozilla 官方下载降级后重新执行完整发布验收；
- 官网不得引用 `alpha.2` 标签或失败流水线中的临时构建物。

### 2026-09-29 alpha.3 候选阻断记录

- 标签 `v0.1.0-alpha.3` 的发布流水线在 Windows 编译阶段被闸门阻断，没有生成 GitHub Release；
- Firefox 官方下载降级缺少显式 `System.Net.Http` 引用；
- `alpha.4` 补齐引用后重新执行完整发布验收，官网不得引用 `alpha.3` 临时构建物。

### 2026-09-29 alpha.4 候选阻断记录

- 标签 `v0.1.0-alpha.4` 通过编译和载荷校验，但干净 Windows Runner 的 Microsoft Store 源在 Obsidian 安装阶段返回地区协议提示和 `No package found matching input criteria`；
- 发布闸门在生成 Release 前终止，没有公开安装包；
- `alpha.5` 为 Obsidian 增加 Microsoft Store、Windows 软件源、官方发行包三级降级，并重新执行完整验收。

## 不进入 v0.1

- 项目方托管的公共微信机器人（用户自己连接的 ZCode 官方 Bot Channel 属于 v0.1 主流程）；
- 支付、余额、订单和退款；
- 多P批量、合集、直播、番剧与互动视频；
- 公共 Cookie；
- 自动绕过会员、地区限制或 DRM；
- 默认永久保存原视频；
- 自动安装 Obsidian 社区插件；
- 面向公网暴露未经鉴权的 MCP。
