# Windows 手动恢复与 Agent 兜底

本页只用于安装器已经运行，但 Obsidian 没有显示“视知库”仓库、ZCode 没有显示
“视知库助手”工作区，或右侧没有“知识激活”助手的情况。正常安装不需要执行这些步骤。

## 先做无损修复

1. 关闭 Obsidian 和 ZCode；如果它们仍在后台运行，也一并退出。
2. 从 [视知库官网](https://shizhiku.cn/download) 下载当前版本安装器。
3. 重新运行安装器，保持原来的知识库路径不变，点击“安装 / 修复本机”。
4. 修复完成后，先点击“用 Obsidian 打开”，再点击“用 ZCode 打开视知库助手”。
5. Obsidian 首次使用本地助手时，需要在设置中允许社区插件（关闭 Restricted Mode），然后重启一次 Obsidian。

原位修复会保留 Kimi Key、平台登录状态、已有笔记、Vault、ZCode 其他项目和模型配置。
不要卸载软件、删除目录或新建第二个同名 Vault 来代替修复。

## 手动打开 Obsidian 仓库

默认仓库位于当前用户的“文档”目录下，文件夹名为 `视知库`。如果安装时选择过其他目录，
以安装器“Obsidian 知识库”框中显示的路径为准。

1. 打开 Obsidian；
2. 选择“打开文件夹作为仓库”；
3. 选择安装器显示的知识库目录；
4. 确认左侧能看到 `Douyin`、`Bilibili` 或 `Video Notes` 等受管笔记目录；
5. 若右侧仍没有“知识激活”，允许社区插件后重启 Obsidian，再点击右侧星形入口。

不要手工修改 `.obsidian`、`community-plugins.json` 或插件文件。插件缺失时回到安装器执行原位修复。

## 手动打开 ZCode 工作区

默认工作区位于当前用户的“文档”目录下，文件夹名为 `视知库助手`。它应至少包含：

```text
AGENTS.md
README.md
.zcode/config.json
.video-to-obsidian-workspace.json
```

在 ZCode 中选择“打开工作区/打开文件夹”，选择整个 `视知库助手` 目录，不要只打开其中的
`AGENTS.md`，也不要在以前的 `multichannel` 或其他编程项目里连接微信 Bot Channel。

如果目录不存在或缺少上述文件，先执行安装器的“安装 / 修复本机”。高级用户也可以在
PowerShell 中仅重建这个受管工作区：

```powershell
$core = "$env:LOCALAPPDATA\VideoToObsidian\runtime\Scripts\video-to-obsidian.exe"
$workspace = Join-Path ([Environment]::GetFolderPath('MyDocuments')) '视知库助手'
& $core bootstrap-workspace --workspace $workspace --json
& $core onboarding-status --workspace $workspace --json
```

这两条命令不调用付费模型，不读取或显示 Kimi Key，也不修改其他 ZCode 项目。若命令报告目标
目录非空且不是受管工作区，应立即停止，不要强制覆盖。

## 交给本机 Agent 的任务文本

可以把下面整段连同安装器导出的“脱敏诊断报告”交给本机 Agent。不要附带 API Key、Cookie、
验证码或个人视频。

```text
请只修复本机“视知库”安装，不要重装系统，不要删除任何笔记、Vault、浏览器 Profile、
API Key 或 ZCode 项目，也不要修改“视知库助手”以外的 ZCode 配置。

请按顺序执行：
1. 只读检查 %LOCALAPPDATA%\VideoToObsidian\runtime\Scripts\video-to-obsidian.exe 是否存在；
2. 运行 doctor --json 和 onboarding-status --json，输出时不得显示 Secret、Cookie 或完整本机路径；
3. 检查“文档\视知库助手”是否包含 AGENTS.md、README.md、.zcode/config.json 和
   .video-to-obsidian-workspace.json；
4. 若工作区缺失，仅调用 bootstrap-workspace --workspace <该目录> --json 重建受管文件；
5. 不要手工编辑 Obsidian 的 .obsidian。若 Vault 未登记、插件缺失或 Obsidian 正在占用配置，
   请让我关闭 Obsidian/ZCode并重新运行官网当前安装器的“安装 / 修复本机”；
6. 修复后重新运行 doctor 和 onboarding-status，只报告通过项、失败项和下一步；
7. 不调用 analyze_douyin、analyze_bilibili 或 knowledge-run，不产生任何付费调用。

遇到非受管目录、无效 JSON、多个 Vault 无法判断或路径与安装器显示不一致时立即停止并询问，
不得猜测、覆盖或迁移数据。
```

## 更新方式

当前 Alpha 没有静默自动更新。升级时关闭 Obsidian 和 ZCode，从官网下载最新版，运行后点击
“安装 / 修复本机”。安装器会复用原 Vault、专用工作区、平台登录状态和安全保存的 Key。
升级后在安装器底部重新执行免费检查，再做一条真实视频测试。

