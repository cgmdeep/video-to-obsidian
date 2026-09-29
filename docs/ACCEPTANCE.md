# 公开发布验收记录

任何一项没有实际证据，都保持未通过。测试人不得用标题摘要、模拟响应或旧生产环境结果替代干净设备闭环。

## 环境

- [ ] 干净 Windows 11 设备或全新虚拟机；
- [ ] 只下载一个 `VideoToObsidian.Setup.exe`，不预装 Python；
- [x] 记录安装器来源 commit、文件字节数和 SHA256；
- [ ] 当前目标 ZCode 版本及版本号；
- [x] 全新 Firefox `VideoToObsidian` Profile（干净 Runner 自动验收）；
- [x] 全新 Obsidian Vault（干净 Runner 自动验收）；
- [x] 标准版安装、重装和卸载（干净 Runner 自动验收）。

## 普通用户路径

- [x] 双击安装器后，不克隆仓库、不打开 PowerShell 也能完成准备（ROG 临时普通账户图形验收）；
- [ ] “登录抖音”“登录B站”均打开隔离的 `VideoToObsidian` Profile；
- [ ] “用 Obsidian 打开”能打开本次选择的 Vault；
- [ ] 用户能从界面复制 `文档\视知库助手` 路径并在 ZCode 打开；
- [x] ZCode 官方微信 Bot Channel 扫码成功，未安装企业微信或个人微信 Hook；
- [ ] 无 Coding Plan 时，用户自有 Kimi Key 可以提供 ZCode 路由模型；
- [x] 微信发送“检查系统”能获得免费诊断回复；
- [ ] “导出脱敏诊断报告”在桌面生成 JSON，且报告不含 Key、Cookie、Bearer 或签名 URL；
- [ ] 安装器给出的下一步不要求用户理解 Python、MCP、Cookie 文件或终端命令。

## 免费检查

- [x] `doctor --json` 不调用 Kimi；
- [x] `route_video` 正确区分抖音、B站和“使用K3深度分析”；
- [x] 安装、启动、重新检查阶段账户无 token 扣费（自动准备与 `doctor` 均无付费调用）；
- [x] ZCode 只发现一个 `video-to-obsidian` MCP；
- [x] 原有 ZCode MCP 配置未变化（自动验收注入无关 MCP，修复、卸载和重装后均保留）；
- [x] 首次准备的进度、配置和空 Vault 不出现 Key、Cookie、签名 URL；
- [x] 默认不创建 `.obsidian` 或安装社区插件。

### 2026-09-27 干净 Runner 首次准备

- workflow：[`Windows clean acceptance #36308011099`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36308011099)；
- commit：`9b0a4206608a34c1210444f675e1d0566fb91127`；安装包 71,663,006 字节；SHA256 `e9f8eda8f8bf35b764ed1936ec791f4dc02772192eb850fcbe0cac44409692f6`；
- 安装器通过与图形按钮相同的准备协调器完成运行时、Firefox、Obsidian、ffmpeg、中文 Vault 和专用工作区；
- 首轮验收暴露后台命令无超时，第二轮暴露英文 Windows `cp1252` 无法输出中文；均已修复后通过；
- 结果 JSON：`ok=true`、`vault_created=true`、`workspace_created=true`、`contains_secrets=false`、`paid_call_performed=false`；另验证专用 Firefox Profile、单一 MCP、无 `.obsidian`、配置无疑似 Key/Cookie 字段和免费 `doctor`；
- 不据此勾选 Windows 11 图形点击、扫码、ZCode 微信、卸载或真实视频项目。

### 2026-09-27 ROG 重装与远程维护边界

- 修复 commit：`6a5291c491e4c43db9fe0b54fa4863f48716268f`；干净 Windows 验收 [#36311305132](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36311305132) 通过；
- 新安装包 71,663,166 字节，SHA256 `916a5b563d1305a94b6170188a75454ac959d87a6bc4003690b9a632d65b4a47`；已部署到 ROG，旧包保留为 `VideoToObsidian.Setup.previous.exe`；
- ROG 重复执行与图形按钮同一个准备协调器，结果 `ok=true`、Vault/工作区存在、无敏感信息、无付费调用；
- 暴露的 Windows 边界：SSH 非交互登录会话不能读 Credential Manager，底层返回非 `KeyringError` 的 `pywintypes.error` 并导致旧版 `doctor` 崩溃；
- 修复后 SSH 体检会如实报告“系统钥匙串不可用”而不崩溃，其余依赖全部通过，`paid_call_performed=false`；
- 同一机器的交互用户会话体检 `doctor_ok=true`，Kimi Key 可从 keyring 读取，未显示密钥、未触发付费调用。

### 2026-09-28 旧线稳定性迁移与 ROG 免费验收

- 迁移 commit：`28bee288021f9a54f3dc2dd81431801567d23b1b`；CI、安全扫描和 Windows 3.11/3.12 回归均通过；
- 干净 Windows 首次准备 workflow：[`#36364601578`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36364601578)，从构建 wheel、发布单文件安装器到新用户准备全部通过；
- 安装包 SHA256 `7f04d4cc2e6b206b376cc1e42e0d53ca515118d8961a140d99aab6f8f8aea974`；ROG 升级前已保留 `VideoToObsidian.Setup.pre-reuse-port.exe`；
- ROG 幂等准备返回 `ok=true`、`vault_created=true`、`workspace_created=true`、`contains_secrets=false`、`paid_call_performed=false`；
- Windows 实机制造“父 Python 启动子 Python 后超时”，返回 `command_timeout`、`retryable=false`，子进程确认已清理；
- SSH 非交互体检只报告 Windows Credential Manager 不可用，其余依赖、Vault、Firefox Profile 和受管工作区均通过；该结果不代表交互用户会话中的 keyring 失效。
- 本轮未执行真实视频和 Kimi 调用；B 站 412 公开 API 降级、抖音分享文本元数据恢复、任务锁和 Kimi 尝试账本仍需通过真实样本验收。

### 2026-09-29 ROG 临时普通账户图形验收

- Windows 11 Home 新建本地标准账户 `VTOAcceptance`，从单文件图形安装器点击“安装 / 修复本机”；用户路径未克隆仓库、未打开终端、未提供 Secret，也未调用付费模型；
- 首轮真实点击暴露新账户没有 `winget` 命令别名；commit `888d740` 改为自动定位系统已安装的 App Installer，复测成功进入 Python 安装；
- Obsidian 默认条目从 GitHub 下载较慢；commit `5516f18` 改为优先 Microsoft Store 官方条目，实机完成 1.13.7 下载、验签和安装；
- FFmpeg 完整包约 258 MB；commit `5b0cee5` 改为约 115 MB 的 Essentials Build，仍提供 `ffmpeg`、`ffplay` 和 `ffprobe`；commit `62925f6` 为弱网下载保留 30 分钟边界；
- 最终安装包来自 commit `62925f6`，CI [#36524435554](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36524435554) 与安全检查通过；文件 71,680,234 字节，SHA256 `50368272a31a8b56efe0ed8281ace1752d2961357616121b05f6ee55be1d2548`；
- 图形流程创建隔离运行时、无 Secret 配置、空中文 Vault、专用 ZCode 工作区和单一 MCP，并注册 `VideoToObsidian` Firefox Profile；默认 `save_video=false`、逐字稿关闭且不创建 `.obsidian`；
- 首次联网准备还会下载 Python、Firefox、Obsidian 与 FFmpeg；弱网环境应预留约 1–2 GB 空间和 10–30 分钟，官网和下载页必须明确说明。扫码、真实 Key、真实视频和图形卸载仍按各自验收项单独确认。

### ROG 验收节点守护

ROG 只作为单用户验收和比赛演示节点，不作为多租户云后端。ZCode 官方微信 Bot
依赖已登录的 Windows 图形会话，不能以系统服务替代。

- `scripts/windows-node-monitor.ps1` 只检查本项目运行时、ZCode、磁盘、内存和远程连接服务；
- 守护脚本只在 ZCode 完全退出时重新打开 ZCode，不结束或重启其他项目的 Python 进程；
- `doctor` 仍是免费检查，状态文件明确记录 `paid_call_performed=false`；
- 状态写入 `%LOCALAPPDATA%\VideoToObsidian\state\node-status.json`，不含 Key、Cookie、Bearer、提示词、分享文本或签名媒体 URL；
- `scripts/install-windows-node-monitor.ps1` 注册当前用户登录触发和每 5 分钟重复任务；使用 `-Remove` 可移除任务和脚本，同时保留 Vault、配置、检查点与状态记录。
- 验收节点可显式运行 `scripts/set-windows-node-power.ps1`，只禁用插电状态下的睡眠和休眠；原值写入脱敏基线，使用 `-Restore` 恢复，电池设置始终不变。

#### 2026-09-28 ROG 部署证据

- Windows 11 ROG：15.7GB 内存、C 盘剩余 206.6GB，满足当前单并发验收；部署时未关闭任何其他项目进程；
- 已安装当前用户计划任务 `VideoToObsidian Node Monitor`，登录触发并每 5 分钟运行，`LogonType=Interactive`、`RunLevel=Limited`、`LastTaskResult=0`；
- 交互会话任务生成的状态：`doctor_ok=true`、`kimi_key_ok=true`、`zcode_running=true`，Tailscale、NetBird、sshd 均运行；
- 状态报告敏感模式扫描为阴性，`paid_call_performed=false`，本轮未调用 Kimi、未下载或分析视频；
- 插电睡眠由 600 秒、休眠由 3600 秒调整为关闭；电池设置未改，原值与恢复脚本保存在本机受管 `ops` 目录。

#### 2026-09-29 可选跨设备同步核验

- ROG 的 `kb-notes` Syncthing 目录状态为 `idle`，`globalFiles=143`、`localFiles=143`、`needFiles=0`、`needBytes=0`、`pullErrors=0`，并连接到 1 台同步设备；
- ROG 与 Mac 的有效 Markdown 相对路径集合均为 95 项；Mac 文件系统额外看到的 3 项全部位于 `#SyncVersion/`，是同步历史版本，不是未同步笔记；
- 产品的稳定身份检查已排除 `.obsidian`、`.trash`、`.stversions` 和 `#SyncVersion`，避免把同步软件备份误判为第二份正式笔记；
- Syncthing 管理界面只监听 ROG 的 `127.0.0.1:8384`，诊断后已轮换本地管理令牌并验证进程与监听恢复；
- 此项只证明作者验收环境的可选跨设备同步。公开 Alpha 的基础承诺仍是写入用户选择的本地 Vault，不强制安装 Syncthing、NAS 或其他同步软件。
- ROG 到 Moonshot、B站、抖音的 DNS 与 TCP 443 均通过；经 Tailscale 到 NAS 延迟约 28ms。

#### 2026-09-29 真实 Vault 重复来源审计

- commit `dd5a1aa0fe951ee7efb653ebd47a6cd75f1b064e` 新增只读 `audit-vault --json`；本地 105 项核心测试、CI [`#36546852557`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36546852557) 与 Security [`#36546852523`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36546852523) 均通过；
- ROG 已按该 commit 更新核心，真实 Vault 审计结果：94 个有效 Markdown、3 个受管来源笔记、3 个唯一稳定身份、0 个重复组、0 个不可读文件，`paid_call_performed=false`；
- 同期 Syncthing 再验收为 `idle`、`globalFiles=143`、`localFiles=143`、`needFiles=0`、`needBytes=0`、`pullErrors=0`，连接 1 台同步设备，证明审计时没有待拉取文件；
- 诊断过程中发现磁盘上的 Syncthing XML 尾部格式异常，错误输出曾带出仅限 `127.0.0.1:8384` 的本地管理令牌；令牌已立即轮换，旧令牌被拒绝、新令牌通过，配置已由 Syncthing 重写并经 XML 解析验证有效。未暴露同步数据、设备密钥或公网可用凭据。

## 卸载与恢复

- [x] 重复执行“安装 / 修复本机”的共享准备协调器不会重复创建环境或破坏配置；
- [x] 安装器内置安全卸载能移除安装核心和本项目 MCP；
- [x] 源码中的 `scripts/uninstall.ps1` 能移除安装器核心和本项目 MCP；
- [x] 默认卸载保留 Vault、专用工作区、Firefox Profile、Kimi Key 和检查点；
- [x] 私有数据卸载会删除受管私有运行目录，但仍不删除 Vault；
- [ ] 在存在专用测试 Key 的 Windows Credential Manager 上验证 Kimi Key 实际删除；
- [x] 卸载后不触碰其他 ZCode 配置和 MCP；模型供应商不在卸载器修改范围内。

### 2026-09-29 干净 Windows 生命周期验收

- commit：`c30926fc34c72e370b2bb6a070ecf9ea646d05fc`；workflow：[`Windows clean acceptance #36503042863`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36503042863)；
- `VideoToObsidian.Setup.exe`：71,678,488 字节；SHA256 `c51446235f997c0f8c8e98c49fcda70f2a916fbf7582d4ec01862aec9a6dc0e0`；
- 同一干净 Runner 顺序完成首次安装、原地修复、默认安全卸载、卸载后重装和私有数据卸载；五份结果均 `ok=true`、`contains_secrets=false`、`paid_call_performed=false`；
- 默认卸载后 `core_removed=true`、`managed_mcp_removed=true`，Vault、专用工作区与 Firefox Profile 均保留；预先注入的无关 MCP 在修复、卸载和重装后均存在；
- 私有数据卸载后受管 roaming/local 目录均移除，Vault、工作区、Firefox Profile 和无关 MCP 仍保留；Runner 未注入真实 Key，因此不把该轮视为 Credential Manager 真实删除验收；
- 边界：这是无人值守自动验收，不替代普通用户在 Windows 11 上的图形按钮、SmartScreen 和交互确认验收。

### 2026-09-29 源码卸载补充验收

- commit：`ee58e82f6bf9b1b8ec80db8e31a25d683b76ce9e`；workflow：[`Windows clean acceptance #36537411556`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36537411556)；CI 与 Security 同 commit 均通过；
- 干净 Runner 在安装后先直接执行仓库中的 `scripts/uninstall.ps1`，确认核心与本项目 MCP 被移除，而 Vault、工作区、Firefox Profile 和预先注入的无关 MCP 均保留；随后重新安装并继续通过修复、安装器默认卸载、重装和私有数据卸载；
- 首轮补充验收发现英文 Windows 的旧控制台编码无法输出核心的中文状态文本；修复仅在子 Python 命令期间临时强制 UTF-8，并在命令结束后恢复调用者环境；
- 六份 JSON 报告均 `ok=true`、`contains_secrets=false`、`paid_call_performed=false`；本轮临时安装器为 71,684,315 字节，SHA256 `138b1be4954ec1aa8f0ca139c9f7dbbfcb6a5258ef0c52408d42effdb6407521`。

### 2026-09-29 自定义 Vault 修复与重装验收

- 修复 commit：`cc1a4dd79f97abeeb393ef6730e2bcef15a1e228`；CI、Security 与 [`Windows clean acceptance #36541939024`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36541939024) 均通过；
- 首轮 ROG 升级暴露无界面修复仍使用默认 Vault，安全检查因此正确拒绝复用；首轮干净机固定集又暴露“默认卸载后重装”会忽略被保留的私有配置。两条路径现统一为：配置存在就沿用已配置 Vault 和档位，真正全新安装才使用默认值；
- 干净 Windows Runner 已依次完成首次准备、将配置改为自定义 Vault 与 `transcript` 档位、修复、默认卸载、保留配置重装及私有数据卸载；自定义 Vault 哨兵、无关 MCP、工作区与 Firefox Profile 均按预期保留；
- 验收安装器为 71,685,116 字节，SHA256 `263e4d804fa48c50e6a94225b66094023f1fc295282792e417d7fbc4e353e698`；同一文件已在 ROG 上完成零付费修复，报告 `ok=true`、`vault_created=true`、`workspace_created=true`、`contains_secrets=false`、`paid_call_performed=false`，原自定义 Vault 配置未被改写，ZCode 与受管 MCP 已恢复运行。

## 真实视频闭环

分别选择公开视频，记录视频 URL 的稳定身份，不把 Cookie 或签名媒体地址写入本文件。

| 用例 | 平台/模型 | 时长 | 下载字节 | 输入 token | 输出 token | 实际扣费 | 笔记 | 视频清理/归档 | 结果 |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| 小视频 | 抖音 / K2.7 | 246.07s | 52,220,000 | 42,454 | 2,903 | 约 ¥0.354（按 2026-09-27 官网标准价估算） | 6,978 B，已写入 ROG 新 Vault | `save_video=false`，源文件/代理/检查点均清理 | 通过（2026-09-27） |
| 典型视频 | B站 / K2.7 | 1,244.17s | 127,300,056 | 45,166 | 6,239 | 约 ¥0.462（按 2026-09-29 官网标准价估算） | 12,681 B，已写入 ROG 新 Vault | `save_video=false`，源文件/代理/检查点均清理 | 通过（2026-09-29） |
| 深度档 | B站 / K3 | 待测 | 待测 | 待测 | 待测 | 待测 | 候选路径 | 待测 | 未执行 |
| 长视频 | B站 / K2.7 | 2,221.34s | 360,699,486 | 45,088 | 4,030 | 约 ¥0.402（按 2026-09-28 官网标准价估算） | 11,906 B，已写入 ROG 新 Vault | `save_video=false`，源文件/代理/检查点均清理 | 通过（2026-09-28） |

每次调用前由测试人确认费用。测试完成后根据当日官方单价复核扣费，不写“每条固定价格”。

### 2026-09-27 抖音真实闭环证据

- 设备：独立 Windows 11 ROG 测试机；专用 Firefox `VideoToObsidian` Profile；标准版（逐字稿关闭）。
- yt-dlp 即使读取到新鲜登录 Cookie 仍被抖音返回 HTTP 403；该问题与 yt-dlp 官方列出的 Douyin `fresh cookies` 已知问题一致。
- 修复：按 Firefox `profiles.ini` 解析真实随机目录；抖音在 yt-dlp 失败时，受控回退到专用 Firefox 的浏览器会话，捕获同一单视频的音视频 CDN 请求，在内存中保留签名 URL，分别下载并由 ffmpeg 无重编码合并。
- 媒体校验：H.264、934×720、246.066667 秒，同时包含视频流和音频流；下载授权来源标记为 `firefox_browser`。
- Kimi：`kimi-k2.7-code`，仅调用一次；`finish_reason=stop`；`prompt_tokens=42454`、`completion_tokens=2903`、`reasoning_tokens=1634`。
- 费用：按当日官网 K2.7 Code 输入 ¥6.50/MTok、输出 ¥27.00/MTok计算约 ¥0.354；不是账单实扣值。
- 安全与清理：浏览器 Cookie 只由 Firefox 访问，不转发给媒体 CDN；签名 URL 只留在进程内存；manifest 不含 Cookie 名或签名 CDN 域名；未保存原视频；成功后 `source_path`/`kimi_proxy_path` 为空，检查点目录无残留文件。
- 输出：正式 Markdown 已写入新 Vault 的 `Douyin/`，`schema=kb-source/v1`、稳定身份与 `generated_by` 字段齐全。

### 2026-09-28 B站长视频真实闭环证据

- 设备：独立 Windows 11 ROG 测试机；专用 Firefox `VideoToObsidian` Profile；标准版（逐字稿关闭、`save_video=false`）。
- 样本：公开单分 P 视频，稳定身份 `bilibili_BV12ftJ6rEkw_p01`，时长 2,221.343 秒（约 37 分钟）；登录态元数据和媒体下载均通过，未触发降级重试。
- 媒体：原视频 360,699,486 字节；自动生成覆盖完整时间线的低帧率代理 46,076,182 字节，再提交视觉分析，验证了超过 15 分钟强制代理闸门。
- Kimi：`kimi-k2.7-code`，仅调用一次；`finish_reason=stop`；`prompt_tokens=45088`、`completion_tokens=4030`，其中 `reasoning_tokens=1660`。
- 费用：按当日官网 K2.7 Code 输入 ¥6.50/MTok、输出 ¥27.00/MTok 计算约 ¥0.402；不是账单实扣值。
- 输出：正式 Markdown 11,906 字节，已写入新 Vault 的 `Bilibili/`；任务状态 `completed/finished`，数值型 Kimi 调用历史文件存在。
- 安全与清理：结果、manifest 和正式笔记的敏感模式扫描为阴性；成功后源视频和代理路径均不存在，检查点媒体数为 0；一次性验收计划任务及执行脚本已移除。

### 2026-09-29 B站典型视频单次付费验收

- 用户在调用前明确确认付费测试；样本为公开单分 P 技术科普视频，稳定身份 `bilibili_BV1DWjAzHE2J_p01`，时长 1,244.173 秒（约 20 分 44 秒），调用前不存在 manifest、正式笔记或该身份的 Kimi 历史。
- 设备与档位：ROG Windows 11、专用 Firefox `VideoToObsidian` Profile、标准版；`save_video=false`、逐字稿关闭、模型严格为 `kimi-k2.7-code`。一次性启动锁禁止同一样本再次启动，任务没有自动重试。
- 媒体：下载 127,300,056 字节；超过 15 分钟后生成覆盖完整时间线的低帧率代理 44,547,914 字节。任务成功后源视频和代理均不存在。
- Kimi：仅调用一次；全局历史 `2 → 3`、该身份历史 `0 → 1`；`finish_reason=stop`、`prompt_tokens=45166`、`completion_tokens=6239`，其中 `reasoning_tokens=3360`。
- 费用：2026-09-29 [官方模型推理价格说明](https://platform.kimi.com/docs/pricing/chat)中 K2.7 Code 标准价为缓存未命中输入 ¥6.50/MTok、输出 ¥27.00/MTok；本次 usage 未报告缓存命中，按未命中估算约 ¥0.462。该数值是依据 usage 的估算，不冒充控制台账单实扣值。
- 输出：正式 Markdown 12,681 字节，已写入 Vault 的 `Bilibili/`；manifest 为 `completed/finished`，无同稳定身份的第二份正式笔记。
- 初步人工质量检查：正文按 CRT → LCD → OLED → Mini LED/QD-Mini LED → 选购参数 → 产业结论保持论证顺序；保留刷新率、对比度、色域、分区数、市场份额、专利数、厚度和能耗等参数，争议性产业判断多使用“视频称/视频认为”归属。结构、可读性、数字覆盖和来源归属通过。
- 质量边界：B站没有为该视频提供可下载字幕轨，且本轮没有为了验收临时开启逐字稿；因此尚未把每一句音频与笔记逐字对照，也未独立事实核查视频中的厂商宣传数据。该轮不能单独勾选“多人观点、反讽、音画冲突”等其他固定集维度。

### 2026-09-29 远程 SenseVoice 兼容接口冒烟测试

- ROG 通过 Tailscale 访问既有 ASUS SenseVoice 兼容端点 `100.108.232.36:8010`，TCP 检查通过；测试没有向公网暴露端口。
- 使用 Windows 离线语音合成生成短 WAV，再调用本项目 `transcribe_video` 的远程档位；接口返回非空文本，抽取音频 135,378 字节、转写 50 字符。
- 报告写入 ROG 私有状态目录，标记 `paid_call_performed=false`；临时 WAV 和执行脚本已清理，不含 API Key、ASR Token 或转写正文。
- 此项只验证“远程 SenseVoice 兼容接口 + 本项目适配器”可用，不代表逐字稿增强版已完成真实视频全链路，也不能让公开版依赖作者的 ASUS。公开用户仍需自备本地或私有远程 SenseVoice 服务；一键部署与完整真实视频验收保持待办。

### 2026-09-29 安装器档位切换零付费验收

- commit `e31911a23517f54ccebafaf5b83f2fc2dfbe20f4` 的候选安装器在 ROG 原地修复成功；文件 SHA256 为 `4fe73242ea32a36f4aade610e03dcb930fe6a85818b8841927a36f51160e455b`。CI [`#36555808076`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36555808076) 与 Security [`#36555808096`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36555808096) 全部通过。
- 验收只复制生产配置到临时文件，再执行 `standard → transcript → standard`；两个方向均返回 `changed=true`，标准档体检通过，逐字稿档在未配置 `ASR_URL` 时只报告非必需项不可用，符合“缺少自备 SenseVoice 时不阻断正式笔记”的降级边界。
- 切换实现兼容 Windows：不再调用 Windows 缺失的 `os.fchmod`，并在关闭临时文件句柄后保留权限、原子替换；同时保留原有 CRLF 换行。往返后的临时配置与切换前 SHA256 完全一致。
- 生产配置没有被档位测试改写；测试前后私有状态均为 22 个文件、65,435 字节。报告标记 `paid_call_performed=false`，没有提交视频或调用 Kimi。
- 验收后 Vault 审计为 95 个 Markdown、4 个受管来源笔记、4 个唯一稳定身份、0 个重复组、0 个不可读文件。该项只完成安装器/配置切换验收，逐字稿增强版真实视频闭环仍保持待办。

### 2026-09-29 ZCode 官方微信入口双平台验收

- 入口：用户在微信中向 ROG 上 ZCode 官方 Bot Channel “小Z”主动发送链接；两类消息均进入专用 `视知库助手` 工作区，未使用企业微信回调或个人微信 Hook。
- 抖音：稳定身份 `douyin_7681133341692677414`，时长 205.98 秒；微信路由只调用一次 `analyze_douyin`，Kimi `kimi-k2.7-code` 输入 42,096 tokens、输出 2,577 tokens（其中 reasoning 1,251）；7,252 字节笔记已写入 `Douyin/`，`save_video=false`、逐字稿关闭、未归档原视频。同一链接首次少字母 `h` 时，工具在 19ms 内返回 `missing_video` 且 `retryable=false`，没有进入付费分析。
- B站：稳定身份 `bilibili_BV12ftJ6rEkw_p01`；微信路由只调用一次 `analyze_bilibili`，命中 2026-09-28 已验证缓存，`cached=true`，未新增 Kimi 调用；11,906 字节笔记路径验证存在，原视频未保存。
- 回执：两次都由 ZCode 将工具返回的标题、路径、用量、缓存/降级状态和原视频归档状态回传微信；未由路由模型二次观看或伪造视频结论。

### 2026-09-28 旧线稳定性能力迁移（仅源码回归）

- Windows 命令边界优先使用 Job Object，超时时整组终止 yt-dlp/ffmpeg 及子孙进程；非 Windows 使用独立进程组清理。
- 同一视频使用跨进程互斥锁；重复提交不允许重复下载或调用 Kimi。
- 元数据前创建脱敏 submission receipt；不保存分享文本、URL、Cookie 或签名媒体地址。
- B站增加正常网页请求头、HTTP 412/元数据超时公开 `view/playurl` API 降级、单分P闸门、Range 下载和 yt-dlp 零文件回退。
- `command_timeout` 不再向 ZCode 声明可盲目重试；抖音/B站由平台适配器在单次工具调用内执行受控降级。
- 每次真实 Kimi 尝试写入同步树外不可变数值诊断记录；不含提示词、报告、逐字稿或 reasoning 正文。
- 抖音恢复官方分享文本的标题/作者补全，并显式识别 Firefox 人机验证页。
- 本地回归：`python -m pytest -q` 全部通过。本节不代表 Windows Job Object、B站真实 412 或付费 Kimi 已在 ROG 完成验收。
- 超过15分钟的视频即使源文件未达到上传上限，也会生成覆盖完整时间线的 480×270、2fps 低帧率代理；失败时再降至 426×240、1fps，避免长视频仅因文件较小而直接消耗过多视觉上下文。

## 总结质量固定集

- [x] 时间线和事件顺序；
- [x] 数字、参数、例子与图表；
- [x] 多人物观点归属；
- [x] 反讽与引用归属；
- [ ] 戏仿、夸张和反问（本轮样本未分别冻结这三项）；
- [x] 音频、字幕与画面冲突；
- [x] 长视频低码率代理覆盖完整时间线；
- [x] 用户长期偏好与单次要求的优先关系。

每条由人工对照完整视频，记录遗漏、误归属和过度推断，不只评价文风。

工程侧先用自动测试锁定提示词合同，再于 2026-09-29 用离线合成固定集、67 分钟公开多人辩论和偏好冲突候选完成 3 次单次付费验收。人工判定与用量证据见 [`QUALITY_ACCEPTANCE.md`](QUALITY_ACCEPTANCE.md)。该结论不代表对来源视频中的厂商宣传数据做了独立事实核查。

付费固定集使用 [`QUALITY_ACCEPTANCE.md`](QUALITY_ACCEPTANCE.md) 和可重复的离线生成器 `scripts/build-quality-fixture.ps1`。ROG 生成的 `quality-fixed-set-v1.mp4` 为 1 个 H.264 视频流加 1 个 AAC 音频流，1280×720、85.966 秒、969,584 字节，SHA256 `bdbd8234162f2bd1de463e834eda1d80415c09884c8f4e9e00e26e8a42645d3c`。五段预先冻结多人观点、反讽、音画数字冲突和“引用不等于本人立场”的判据；生成阶段 `paid_call_performed=false`，后续 K2.7 输出已通过全部冻结判据。

## 失败与恢复

- [x] 自动固定集验证 Kimi 输出预算耗尽时只调用一次且保留检查点；
- [x] 自动固定集验证人工重试不重新下载，已完成逐字稿时也不重复转写；
- [x] HTTP 412/429/5xx/连接中断最多由上层重试一次；
- [x] 自动固定集验证正式笔记已存在时，K3 或偏好变更只生成 Vault 外候选；
- [x] 失败状态不会被报告为已保存或已归档；
- [x] 标准版成功后不残留视频、代理或临时音频；
- [x] 自动固定集验证增强版 ASR 可选失败时降级、必需失败时在 Kimi 前停止并保留来源检查点；真实远程 SenseVoice 兼容接口冒烟通过，增强版真实视频全链路仍待验收。

### 2026-09-29 无费用队列与失败回执固定集

- 全部 102 项核心测试通过；新增 100 个同时提交的 MCP 任务压测，处理节点实测最大并发为 1，所有任务均完成且 `paid_call_performed=false`；
- 412 由平台适配器执行单次受控降级；429、500、503 和连接中断在工具内不自动重试，只返回带 `kimi_attempts=1` 的可重试错误，工作区规则最多允许上层再试一次；
- 失败 MCP 回执固定为 `ok=false`、`complete=false`、`status=failed`，不包含 `saved_to` 或 `archived_video`；未知异常只返回脱敏的 `internal_error`，不复制底层异常正文；
- 此轮证明单节点排队与错误边界，不替代真实网络抖动、平台登录失效、20 人体验或付费 Kimi 稳定性验收。

### 2026-09-29 磁盘空间前置闸门与平台只读抽样

- commit `63e50dafe0a076182791ece093117c86b7f6a9c2` 在没有可复用来源检查点时，先验证检查点盘至少剩余 1 GiB；不足时返回 `insufficient_disk_space`，并在任何下载和 Kimi 调用前停止；
- 自动固定集验证错误详情只含阶段、所需字节和可用字节，submission receipt 为 `paid_call_performed=false`，下载与 Kimi 调用次数均为 0；全部 106 项核心测试、CI [`#36547669913`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36547669913) 与 Security [`#36547669893`](https://github.com/cgmdeep/video-to-obsidian/actions/runs/36547669893) 均通过；
- ROG 已更新至该 commit，再次运行真实 Vault 审计仍为 0 个重复组、0 个不可读文件；B站固定长样本只读元数据抽样返回稳定身份 `bilibili_BV12ftJ6rEkw_p01`、时长 2221.343 秒、`download_auth=firefox_profile`、无降级，`paid_call_performed=false`；
- 更新后终止旧的受管 MCP 进程，使 ZCode 下次调用按新运行时重新启动；未结束或修改其他项目的 Python 进程。

### 2026-09-29 B站完成态缓存 30 轮稳定性巡检

- ROG 对固定完成态身份 `bilibili_BV12ftJ6rEkw_p01` 连续执行 30 轮，轮间隔 60 秒，总时段为 17:37:45–18:07:53；巡检依赖层硬阻断 Kimi 阶段，一旦缓存前置条件或历史计数变化即失败。
- 30/30 均返回 `cached=true`；Kimi 历史计数 `1 → 1`，最终报告 `paid_call_performed=false`、`all_cached=true`，没有新增模型调用。
- 单轮耗时 2.047–3.875 秒，平均 2.279 秒；进程工作集范围 16,723,968–39,337,984 字节（峰值约 37.5 MiB），未观察到随轮次持续增长。
- 测试窗口内检查点盘可用空间净变化约 -9.82 MiB；ROG 同时运行其他服务，因此不把整机空间变化归因于本项目。最终 manifest 仍为 `completed/finished`，`source_path` 与 `kimi_proxy_path` 均为空且对应文件不存在。
- 结束后没有匹配巡检命令的 Python/ffmpeg/yt-dlp 进程；专用 `VideoToObsidian Cache Soak` 计划任务与临时审计脚本已注销/清理，保留脱敏 JSON 报告作为证据。
- 此轮证明重复完成态提交的缓存稳定性，不替代 20 人并发体验、真实付费服务故障或平台 Cookie 失效的长时间运行验收。
