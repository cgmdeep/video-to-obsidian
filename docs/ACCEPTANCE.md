# 公开发布验收记录

任何一项没有实际证据，都保持未通过。测试人不得用标题摘要、模拟响应或旧生产环境结果替代干净设备闭环。

## 环境

- [ ] 干净 Windows 11 设备或全新虚拟机；
- [ ] 只下载一个 `VideoToObsidian.Setup.exe`，不预装 Python；
- [x] 记录安装器来源 commit、文件字节数和 SHA256；
- [ ] 当前目标 ZCode 版本及版本号；
- [x] 全新 Firefox `VideoToObsidian` Profile（干净 Runner 自动验收）；
- [x] 全新 Obsidian Vault（干净 Runner 自动验收）；
- [ ] 标准版安装、重装和卸载。

## 普通用户路径

- [ ] 双击安装器后，不克隆仓库、不打开 PowerShell 也能完成准备；
- [ ] “登录抖音”“登录B站”均打开隔离的 `VideoToObsidian` Profile；
- [ ] “用 Obsidian 打开”能打开本次选择的 Vault；
- [ ] 用户能从界面复制 `文档\视知库助手` 路径并在 ZCode 打开；
- [ ] ZCode 官方微信 Bot Channel 扫码成功，未安装企业微信或个人微信 Hook；
- [ ] 无 Coding Plan 时，用户自有 Kimi Key 可以提供 ZCode 路由模型；
- [ ] 微信发送“检查系统”能获得免费诊断回复；
- [ ] “导出脱敏诊断报告”在桌面生成 JSON，且报告不含 Key、Cookie、Bearer 或签名 URL；
- [ ] 安装器给出的下一步不要求用户理解 Python、MCP、Cookie 文件或终端命令。

## 免费检查

- [x] `doctor --json` 不调用 Kimi；
- [x] `route_video` 正确区分抖音、B站和“使用K3深度分析”；
- [x] 安装、启动、重新检查阶段账户无 token 扣费（自动准备与 `doctor` 均无付费调用）；
- [x] ZCode 只发现一个 `video-to-obsidian` MCP；
- [ ] 原有 ZCode MCP 配置未变化；
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
- ROG 到 Moonshot、B站、抖音的 DNS 与 TCP 443 均通过；经 Tailscale 到 NAS 延迟约 28ms。

## 卸载与恢复

- [x] 重复执行“一键准备本机”的共享准备协调器不会重复创建环境或破坏配置；
- [ ] 源码中的 `scripts/uninstall.ps1` 能移除安装器核心和本项目 MCP；
- [ ] 默认卸载保留 Vault、专用工作区、Firefox Profile、Kimi Key 和检查点；
- [ ] `-RemovePrivateData` 会删除 Kimi Key 和私有运行数据，但仍不删除 Vault；
- [ ] 卸载后不触碰其他 ZCode 工作区、模型供应商和 MCP。

## 真实视频闭环

分别选择公开视频，记录视频 URL 的稳定身份，不把 Cookie 或签名媒体地址写入本文件。

| 用例 | 平台/模型 | 时长 | 下载字节 | 输入 token | 输出 token | 实际扣费 | 笔记 | 视频清理/归档 | 结果 |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| 小视频 | 抖音 / K2.7 | 246.07s | 52,220,000 | 42,454 | 2,903 | 约 ¥0.354（按 2026-09-27 官网标准价估算） | 6,978 B，已写入 ROG 新 Vault | `save_video=false`，源文件/代理/检查点均清理 | 通过（2026-09-27） |
| 小视频 | B站 / K2.7 | 待测 | 待测 | 待测 | 待测 | 待测 | 待测 | 待测 | 未执行 |
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

- [ ] 时间线和事件顺序；
- [ ] 数字、参数、例子与图表；
- [ ] 多人物观点归属；
- [ ] 反讽、引用、戏仿、夸张和反问；
- [ ] 音频、字幕与画面冲突；
- [x] 长视频低码率代理覆盖完整时间线；
- [ ] 用户长期偏好与单次要求的优先关系。

每条由人工对照完整视频，记录遗漏、误归属和过度推断，不只评价文风。

## 失败与恢复

- [ ] Kimi 输出预算耗尽时只调用一次且保留检查点；
- [ ] 人工重试不重新下载、不重复转写；
- [ ] HTTP 412/429/5xx/连接中断最多由上层重试一次；
- [ ] 正式笔记已存在时，K3 只生成 Vault 外候选；
- [ ] 失败状态不会被报告为已保存或已归档；
- [x] 标准版成功后不残留视频、代理或临时音频；
- [ ] 增强版 ASR 失败时按配置正确降级或停止。
