import { App, FuzzySuggestModal, ItemView, Notice, Plugin, PluginSettingTab, Setting, TFile, WorkspaceLeaf, normalizePath } from "obsidian";
import { spawn } from "child_process";
import { existsSync } from "fs";
import { join } from "path";
import { homedir, platform } from "os";

type Operation = "ask" | "compare" | "knowledge_card" | "action_list";
type Mode = "standard" | "deep";
const VIEW_TYPE = "shizhiku-knowledge-activation";
const OPERATIONS: Array<{ value: Operation; label: string; description: string }> = [
  { value: "ask", label: "提问", description: "从一篇笔记中提炼回答" },
  { value: "compare", label: "对比", description: "找出两篇笔记的共识与分歧" },
  { value: "knowledge_card", label: "知识卡", description: "整理成可复用的知识卡片" },
  { value: "action_list", label: "行动清单", description: "转换为可执行的下一步" }
];

interface SettingsData { derivedFolder: string; }
interface RunResult {
  ok: boolean;
  error?: string;
  model?: string;
  result_filename?: string;
  result_markdown?: string;
  usage?: Record<string, number>;
}
const DEFAULT_SETTINGS: SettingsData = { derivedFolder: "Video Notes/Derived" };

export default class ShizhikuPlugin extends Plugin {
  settings: SettingsData = DEFAULT_SETTINGS;

  async onload(): Promise<void> {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    this.registerView(VIEW_TYPE, (leaf) => new KnowledgeView(leaf, this));
    this.addRibbonIcon("sparkles", "知识激活助手", () => void this.activate());
    this.addCommand({ id: "open-knowledge-activation", name: "打开知识激活助手", callback: () => void this.activate() });
    this.addSettingTab(new LocalSettingTab(this.app, this));
    this.app.workspace.onLayoutReady(() => void this.activate());
  }

  onunload(): void { this.app.workspace.detachLeavesOfType(VIEW_TYPE); }
  async saveSettings(): Promise<void> { await this.saveData(this.settings); }

  async activate(): Promise<void> {
    let leaf = this.app.workspace.getLeavesOfType(VIEW_TYPE)[0];
    if (!leaf) {
      leaf = this.app.workspace.getRightLeaf(false) ?? this.app.workspace.getLeaf(true);
      await leaf.setViewState({ type: VIEW_TYPE, active: true });
    }
    this.app.workspace.revealLeaf(leaf);
  }

  private executable(): string {
    if (platform() !== "win32") throw new Error("当前安装包仅支持 Windows 本机助手。");
    const local = process.env.LOCALAPPDATA;
    const candidates = [
      local ? join(local, "VideoToObsidian", "runtime", "Scripts", "video-to-obsidian.exe") : "",
      join(homedir(), "AppData", "Local", "VideoToObsidian", "runtime", "Scripts", "video-to-obsidian.exe")
    ].filter(Boolean);
    const found = candidates.find((candidate) => existsSync(candidate));
    if (!found) throw new Error("未找到视知库本机核心，请运行安装器的“修复本机”。");
    return found;
  }

  async run(operation: Operation, mode: Mode, question: string, files: TFile[]): Promise<{ file: TFile; result: RunResult }> {
    const sources = await Promise.all(files.map(async (file) => ({ name: file.path, markdown: await this.app.vault.read(file) })));
    const request = JSON.stringify({ operation, mode, question: question.trim(), sources });
    const result = await this.invoke(request);
    if (!result.ok || !result.result_filename || !result.result_markdown) throw new Error(result.error || "本机核心没有返回完整结果。");
    const folder = normalizePath(this.settings.derivedFolder.trim() || "Video Notes/Derived");
    await this.ensureFolder(folder);
    const basename = result.result_filename.replace(/\\/g, "/").split("/").pop() || "衍生知识.md";
    let path = normalizePath(`${folder}/${basename}`);
    if (this.app.vault.getAbstractFileByPath(path)) path = path.replace(/\.md$/i, `-${Date.now()}.md`);
    const file = await this.app.vault.create(path, result.result_markdown);
    await this.app.workspace.getLeaf(false).openFile(file);
    return { file, result };
  }

  private invoke(input: string): Promise<RunResult> {
    return new Promise((resolve, reject) => {
      const child = spawn(this.executable(), ["knowledge-run", "--json"], { windowsHide: true, shell: false, stdio: ["pipe", "pipe", "pipe"] });
      const stdout: Buffer[] = [];
      const stderr: Buffer[] = [];
      let size = 0;
      const timer = setTimeout(() => { child.kill(); reject(new Error("知识生成超时，已停止本次调用。")); }, 25 * 60 * 1000);
      child.stdout.on("data", (chunk: Buffer) => {
        size += chunk.length;
        if (size > 12 * 1024 * 1024) { child.kill(); reject(new Error("本机核心返回内容过大。")); return; }
        stdout.push(chunk);
      });
      child.stderr.on("data", (chunk: Buffer) => { if (stderr.reduce((n, item) => n + item.length, 0) < 65536) stderr.push(chunk); });
      child.on("error", (error) => { clearTimeout(timer); reject(error); });
      child.on("close", (code) => {
        clearTimeout(timer);
        const text = Buffer.concat(stdout).toString("utf8").trim();
        try {
          const result = JSON.parse(text) as RunResult;
          if (code !== 0 || !result.ok) reject(new Error(result.error || "知识生成失败。")); else resolve(result);
        } catch (error) {
          const detail = Buffer.concat(stderr).toString("utf8").trim();
          reject(new Error(detail || (error instanceof Error ? error.message : "无法解析本机核心返回。")));
        }
      });
      child.stdin.end(input, "utf8");
    });
  }

  private async ensureFolder(path: string): Promise<void> {
    let current = "";
    for (const part of normalizePath(path).split("/").filter(Boolean)) {
      current = current ? `${current}/${part}` : part;
      if (!this.app.vault.getAbstractFileByPath(current)) await this.app.vault.createFolder(current);
    }
  }
}

class Picker extends FuzzySuggestModal<TFile> {
  constructor(app: App, private files: TFile[], private choose: (file: TFile) => void) { super(app); this.setPlaceholder("搜索笔记标题或路径……"); }
  getItems(): TFile[] { return this.files; }
  getItemText(file: TFile): string { return file.path; }
  onChooseItem(file: TFile): void { this.choose(file); }
}

class KnowledgeView extends ItemView {
  private operation: Operation = "ask";
  private mode: Mode = "standard";
  private question = "";
  private selected: string[] = [];
  private running = false;
  private status = "";
  constructor(leaf: WorkspaceLeaf, private plugin: ShizhikuPlugin) { super(leaf); }
  getViewType(): string { return VIEW_TYPE; }
  getDisplayText(): string { return "知识激活"; }
  getIcon(): string { return "sparkles"; }
  async onOpen(): Promise<void> { this.useCurrent(); this.render(); }
  private useCurrent(): void {
    if (this.selected.length) return;
    const active = this.app.workspace.getActiveFile();
    const fallback = this.app.vault.getMarkdownFiles()[0];
    if (active?.extension === "md") this.selected = [active.path]; else if (fallback) this.selected = [fallback.path];
  }
  private render(): void {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty(); container.addClass("shizhiku-knowledge-view");
    const header = container.createDiv({ cls: "szk-header" });
    const title = header.createDiv(); title.createEl("h2", { text: "知识激活" }); title.createEl("p", { text: "把已有笔记变成新结论" });
    const badge = header.createDiv({ cls: "szk-badge" }); badge.createSpan({ cls: "szk-dot" }); badge.createSpan({ text: "本机已连接" });
    const files = this.app.vault.getMarkdownFiles().sort((a, b) => a.path.localeCompare(b.path));
    const content = container.createDiv({ cls: "szk-content" });
    this.heading(content, "来源", "只会发送你明确选择的笔记");
    const required = this.operation === "compare" ? 2 : 1;
    for (let index = 0; index < required; index += 1) {
      const file = this.selected[index] ? this.app.vault.getAbstractFileByPath(this.selected[index]) : null;
      const button = content.createEl("button", { cls: "szk-source", text: file instanceof TFile ? `${file.basename}  ·  更换` : index ? "＋ 添加第二篇笔记" : "＋ 选择来源笔记" });
      button.onclick = () => new Picker(this.app, files.filter((item) => !this.selected.includes(item.path) || item.path === this.selected[index]), (item) => { this.selected[index] = item.path; this.render(); }).open();
    }
    this.heading(content, "想生成什么", "");
    const grid = content.createDiv({ cls: "szk-grid" });
    for (const option of OPERATIONS) {
      const button = grid.createEl("button", { text: option.label, cls: this.operation === option.value ? "is-active" : "" });
      button.title = option.description; button.onclick = () => { this.operation = option.value; if (option.value !== "compare") this.selected = this.selected.slice(0, 1); this.render(); };
    }
    content.createEl("p", { text: OPERATIONS.find((item) => item.value === this.operation)?.description || "", cls: "szk-muted" });
    this.heading(content, "你想重点关注什么？", "可选");
    const question = content.createEl("textarea", { cls: "szk-question" }); question.rows = 5; question.placeholder = "例如：重点比较证据链、结论边界和可执行建议"; question.value = this.question; question.oninput = () => { this.question = question.value; };
    this.heading(content, "分析强度", "费用按实际 token 计算");
    const modes = content.createDiv({ cls: "szk-grid" });
    for (const [value, label] of [["standard", "标准\nKimi K2.7 · 日常推荐"], ["deep", "深度\nKimi K3 · 复杂推理"]] as Array<[Mode, string]>) {
      const button = modes.createEl("button", { text: label, cls: this.mode === value ? "is-active" : "" }); button.onclick = () => { this.mode = value; this.render(); };
    }
    if (this.status) content.createDiv({ text: this.status, cls: "szk-status" });
    const footer = container.createDiv({ cls: "szk-footer" }); footer.createDiv({ text: "仅处理已选笔记 · 结果另存为新文件", cls: "szk-muted" });
    const run = footer.createEl("button", { text: this.running ? "正在生成……" : "生成衍生知识", cls: "mod-cta szk-run" }); run.disabled = this.running || this.selected.length !== required; run.onclick = () => void this.generate();
  }
  private heading(container: HTMLElement, name: string, hint: string): void { const row = container.createDiv({ cls: "szk-heading" }); row.createEl("strong", { text: name }); if (hint) row.createSpan({ text: hint }); }
  private async generate(): Promise<void> {
    if (this.running) return; this.running = true; this.status = `正在用 ${this.mode === "deep" ? "Kimi K3" : "Kimi K2.7"} 分析，请勿重复点击……`; this.render();
    try {
      const required = this.operation === "compare" ? 2 : 1;
      const files = this.selected.slice(0, required).map((path) => this.app.vault.getAbstractFileByPath(path)).filter((file): file is TFile => file instanceof TFile);
      if (files.length !== required) throw new Error("请先选择来源笔记。");
      const { file, result } = await this.plugin.run(this.operation, this.mode, this.question, files);
      const usage = result.usage || {}; this.status = `已生成：${file.basename}${usage.prompt_tokens || usage.completion_tokens ? ` · tokens ${usage.prompt_tokens || 0}/${usage.completion_tokens || 0}` : ""}`; new Notice("衍生知识已保存。");
    } catch (error) { this.status = `生成失败：${error instanceof Error ? error.message : String(error)}`; new Notice(this.status); }
    finally { this.running = false; this.render(); }
  }
}

class LocalSettingTab extends PluginSettingTab {
  constructor(app: App, private plugin: ShizhikuPlugin) { super(app, plugin); }
  display(): void {
    this.containerEl.empty(); new Setting(this.containerEl).setName("视知库·知识激活").setHeading();
    new Setting(this.containerEl).setName("衍生知识目录").setDesc("问答、对比、知识卡和行动清单的保存位置。").addText((text) => text.setValue(this.plugin.settings.derivedFolder).onChange(async (value) => { this.plugin.settings.derivedFolder = value.trim() || DEFAULT_SETTINGS.derivedFolder; await this.plugin.saveSettings(); }));
    new Setting(this.containerEl).setName("本机执行").setDesc("笔记只会在你点击生成后，通过本机核心发给 Kimi；API Key 从系统凭据库读取，不保存在 Vault。");
  }
}
