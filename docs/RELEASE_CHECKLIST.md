# v0.1 Alpha 发布门槛

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
- 每周依赖漏洞审计、完整 Git 历史 Gitleaks 扫描和 Dependabot；
- 私密漏洞报告说明（功能需在仓库公开时启用）；
- Windows 可选 winget 依赖安装、专用 Firefox Profile 检查和安全卸载脚本；
- 人类安装扫码指南与可复现公开验收记录模板。

## 公开前必须完成

- [x] 加入 Apache License 2.0，并在 Python 包元数据中声明。
- [ ] 使用一台不含作者私人配置的 Windows 11 设备跑完整安装。
- [ ] 核验目标 ZCode 版本的 stdio MCP 配置字段。
- [ ] 验证 Firefox 专用 Profile 名称能被 yt-dlp 正确读取。
- [ ] 分别用一条小型抖音和B站公开视频完成真实下载。
- [ ] 经用户明确同意后，分别完成一次真实 K2.7 付费分析。
- [ ] 验证无逐字稿标准版和远程 SenseVoice 增强版。
- [ ] 验证Kimi失败后复用检查点，不重复下载。
- [ ] 验证笔记、缓存、state、candidate和archive物理隔离。
- [x] CI 使用 Gitleaks 扫描完整 Git 历史，并使用 pip-audit 审计依赖。
- [ ] 仓库切换公开时启用 GitHub Private Vulnerability Reporting，并验证匿名访问者能看到报告按钮。
- [ ] 完成真实付费样本后，在验收记录中填写 usage、当日单价与实际扣费；README 不写死每条价格。
- [ ] 核验 README 中模型名称、充值规则和外部安装说明在发布当天仍有效。

## 不进入 v0.1

- 公共微信机器人；
- 支付、余额、订单和退款；
- 多P批量、合集、直播、番剧与互动视频；
- 公共 Cookie；
- 自动绕过会员、地区限制或 DRM；
- 默认永久保存原视频；
- 自动安装 Obsidian 社区插件；
- 面向公网暴露未经鉴权的 MCP。
