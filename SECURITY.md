# Security Policy

## 不应提交的内容

- Kimi API Key；
- 抖音、B站或其他网站 Cookie；
- MCP Bearer token；
- 浏览器 Profile 或 Cookie 数据库；
- 签名媒体 URL；
- 用户视频、逐字稿、笔记和运行 manifest；
- 私有服务器地址、个人目录和 NAS 凭据。

发现泄露时，应立即删除或轮换对应凭据，并检查完整 Git 历史。仅删除工作区文件不能从 Git 历史中移除秘密。

## 漏洞报告

仓库公开后，请打开 **Security → Advisories → Report a vulnerability**，通过 GitHub Private Vulnerability Reporting 私密提交。该按钮尚未出现时，说明公开发布配置尚未完成；此时不要创建包含复现细节的公开 Issue。维护者确认问题前，请勿公开复现仓库或粘贴密钥、Cookie、用户视频和个人信息。

报告最好包含：

- 受影响版本或提交；
- 最小复现步骤；
- 可能泄露或被修改的数据类型；
- 已采取的临时缓解措施；
- 联系方式（可选）。

维护者会优先确认涉及密钥、Cookie、任意文件覆盖、命令注入和未授权网络暴露的问题。若怀疑凭据已泄露，请先在对应平台轮换凭据，不要等待修复。

## 支持范围

当前只为最新 `main` 和最新发布的 Alpha 版本提供安全更新。第三方软件、平台风控、用户自行修改的 Cookie 获取方式和个人微信 Hook 不在支持范围内。
