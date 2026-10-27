# AutoShop Bridge Agent Skill

[English](#english) | [简体中文](#简体中文)

## English

## **Let AI read and edit Inovance AutoShop projects directly!**

**Bring vibe coding to PLC development and leave repetitive copy-and-paste behind.**

### Install in one sentence

Place this **complete Skill folder** at `.agents/skills/autoshop-bridge/` in your Codex project, then invoke `$autoshop-bridge`.

### Minimal use

Tell your AI where the project is and what to change:

```text
$autoshop-bridge Scan C:\PLC\Demo and summarize its programs and variable tables.

Add a comment to the specified ST program in Editor Mode; do not save yet.
```

Use a supported local Windows AI client with command access. Give the exact project path; ask for saved edits when you want files written.

### Two editing modes

| | Direct File Mode — Method 1 | Editor Mode — Method 2 |
| --- | --- | --- |
| Where changes occur | Native files on disk | The open AutoShop editor buffer |
| Requirements | Can work with the project closed | Local Windows desktop and the target project open; target tabs can be opened/switched automatically |
| Strength | Fast saved-content reads and offline batch edits | Keep the project open; supported source insertions/deletions; AutoShop handles metadata when saving |
| Limits | Cannot see unsaved buffers; legacy writers preserve LF count; the separate closed-project offline workflow supports qualified ST/FB line edits and typed declarations | Full-table reads can take seconds; guarded writes can take tens of seconds |
| Save/reload | Writing changes the disk; tested FB/FC/structure/global-table edits require reopening the project to load | Default is buffer-only; explicit saving writes native files after backup and verification |

The two paths support offline processing and editing inside an open project. Existing program identifiers remain `file` and `editor`; descriptive names do not change commands or APIs.

Common combinations:

- **Daily AI development:** read saved content from files → write through the editor → save if requested → verify → user compiles. Live identity/baseline checks still apply.
- **Offline batch:** user closes the project → file reads/writes → user reopens, checks and compiles.
- **Read-only analysis:** use file queries first; read the editor when unsaved content matters. Protect unsaved user changes and resolve baseline differences before writing.

### Requirements and scope

Python 3.9+; runtime uses only the standard library. Editor Mode additionally needs Windows PowerShell/.NET and AutoShop in the same interactive desktop session. The original backend was tested with **Windows 10 / AutoShop V4.11.0.5 / Python 3.9.1**; this is not fresh-machine, Python 3.12, Claude Code or all-client acceptance.

Supported: identified ST, ST-backed FB/FC, bounded project queries, limited variables/structures/global tables/instances, backups and guarded writes. Separate experimental readers inspect saved LD programs/FBs and ordinary open diagrams: networks, elements, connections, FB call pins and local variables. See [read-only ladder workflow](references/ladder-reading.md). Default scan still only identifies LD; mixed diagrams with embedded ST do not have complete live graph reading. No ladder edits, hardware configuration, PLC download/start/stop/forced IO or automatic compilation. System definitions require the user's installed XML. See [capability and evidence matrix](references/capabilities.md).

### Installation details and client compatibility

| Client | Project-level setup |
| --- | --- |
| Codex, including Codex in the ChatGPT desktop app | Place this **complete folder** at `.agents/skills/autoshop-bridge/` in your project, open a session in that project and invoke `$autoshop-bridge`. |
| Claude Code on the local Windows machine | Place this **complete folder** at `.claude/skills/autoshop-bridge/` in your project, start Claude Code there and invoke `/autoshop-bridge`; this package has not yet been tested in Claude Code. |

Keep `SKILL.md`, `backend/`, references and the manifest together. These paths are client-specific; ordinary ChatGPT/Claude web chats have no supplied local AutoShop integration in this preview. Optional user-wide locations are `~/.agents/skills/autoshop-bridge/` for current Codex and `~/.claude/skills/autoshop-bridge/` for Claude Code; installation is the user's choice, never performed by this Skill.

Install a clean exported package in a new directory. A Git clone containing `.git/`, extra files or Python caches fails the strict bundle check; keep repository metadata outside the installed Skill. On failure, preserve the installation and follow [deployment diagnostics](references/environment.md#安装完整性失败); do not delete unknown files or alter the manifest to bypass verification.

Codex discovers project skills from its working directory and repository ancestors, not arbitrary child projects. If discovery is missing, check the directory/layout and start a new session or restart the client. The development repository's small discovery adapter depends on this full folder and is not a standalone distribution. Client discovery rules: [Codex](https://learn.chatgpt.com/docs/build-skills), [Claude Code](https://code.claude.com/docs/en/skills). Documented installation is distinct from tested runtime compatibility.

### Package, verification and troubleshooting

| Path | Purpose |
| --- | --- |
| SKILL.md | AI routing and reliable workflow |
| references/ | On-demand source/data operations, environment, errors and acceptance |
| backend/ | Generated runtime snapshot from the single maintained backend source |
| scripts/check_bundle.py | Read-only resource/hash verification, not a signature |
| examples/offline_smoke.py | Two synthetic projects, CLI checks, relocation, backups and restore |
| bundle-manifest.json | Version, source/export hashes and documented redaction |

Using the absolute loaded Skill directory as `$skill`, run these separately and check each result; `$out` must be a new absolute output directory outside the installation:

```powershell
python -B "$skill/scripts/check_bundle.py"
python -B "$skill/examples/offline_smoke.py" --output $out
```

See [two-project acceptance steps](references/validation.md). The smoke test creates synthetic fixtures only, never opens AutoShop and never compiles. Independent AI trials completed ST/FC tasks; implicit client discovery and two real-project IDE trials remain untested. Trial results belong in separate development records, not in the AI's routine instructions. Compilation and device behavior are separate evidence stages.

For failure, retain the JSON error, completed stage and backup path; inspect current state before retrying. Do not save stale windows or assume rollback. See [environment and recovery](references/environment.md). This package includes no precompiled development cache: grid access uses the supported PowerShell/fixed-C# fallback. It needs no always-on service or MCP, and exposes no unified progress/cancellation API.

Distribution model **B: portable bundled runtime**. Backend code is generated from one maintained source, not a separately evolved implementation. Customer projects, screenshots, vendor XML, private paths and development history are excluded by the export list and known-pattern checks; these checks do not guarantee semantic anonymization. The repository is public and the complete package is released under the [MIT License](LICENSE). AutoShop itself and vendor materials are not included.

### License

[MIT](LICENSE), copyright 2026 shaying526. The license covers this project; AutoShop and vendor materials retain their own terms.

### Version notes

s15 adds offline ST edits with observed nonzero fold metadata, including line insertion and deletion. An independent 37-to-28-line MAIN candidate passed full readback and zero-error compilation; see [validation](references/validation.md).

s14 adds editor first/second instances in recognized empty FBI tables and deletion to the observed empty profile in both modes. Save/reopen/full-readback and restoration compilation were verified in an independent copy; see [validation](references/validation.md).

s13 includes the MIT license in the complete package and integrity manifest; backend behavior is unchanged.

s12 adds existing structure member renames with associated native initializer-key updates. Source references remain under the caller’s control.

Backend **1.03** · Skill **2026-10-27.s15**. Detailed operation limits and evidence: [capabilities](references/capabilities.md), [validation](references/validation.md).

s11 adds scalar FC declarations in both modes, including the first variables of an empty table. Independent AutoShop copies passed save/reopen/full-readback and zero-error compilation. FC additions require `initial_value: null`; offline edits preserve the complete body and existing records.

s10 fixes stale-mirror rejection in the explicit body registration-receipt route. A locked HCP is still unreadable; the existing target is checked using the closed direct-HCP snapshot, live process/tree, all frozen files and clean editor content. Mirror differences remain advisory. Saving still invalidates the receipt. Independent-copy capture/open/read/edit/save/full-readback passed; no compilation was requested or performed in this fix.

s9 fixes a conservative rejection of literal `=` in structure-member comments. Independent AutoShop V4.11.0.5 copies verified INOUT ports and structured globals through IDE saves, offline writes, full readback and zero-error compilation. Other unobserved delimiters and nonzero unknown ST row fields remain rejected; a multi-target request can still be blocked elsewhere. See [offline editing](references/offline-editing.md).

## 简体中文

## **让 AI 直接读写汇川 AutoShop 工程！**

**把 vibe coding 带入 PLC 开发，告别反复复制粘贴。**

### 一句话安装

把本 Skill **完整目录**放入 Codex 项目的 `.agents/skills/autoshop-bridge/`，然后输入 `$autoshop-bridge`。

### 最简单的使用方式

告诉 AI 工程位置和要做的改动即可：

```text
$autoshop-bridge 扫描 C:\PLC\Demo，汇总程序和变量表。

用编辑器模式给指定 ST 程序加一条注释，先不要保存。
```

使用具备本机命令能力的 Windows AI 客户端，提供准确工程路径；需要落盘时明确要求保存。

### 两种编辑模式

| 对比 | 文件直改模式——方法一 | 编辑器操作模式——方法二 |
| --- | --- | --- |
| 修改位置 | 磁盘上的AutoShop原生文件 | 已打开AutoShop的编辑器缓冲区 |
| 打开要求 | 可以在工程关闭时操作 | 需要本机Windows和目标工程打开；工具可自动打开、切换目标标签 |
| 优势 | 已保存内容读取快，适合离线批量处理 | 工程保持打开，支持限定正文增删行，保存时由AutoShop处理元数据 |
| 限制 | 看不到未保存内容；旧入口同LF，独立offline入口支持已识别ST/FB增删行及类型声明，未知布局拒绝 | 整表读取可能数秒，安全写入可能数十秒 |
| 保存与重载 | 写入即改变磁盘；已验FB/FC/结构/GVT改后须重开工程加载 | 默认只改缓冲，明确保存才在备份和校验后写原生文件 |

两种模式分别服务离线处理与工程打开时的迭代。程序中的标识仍为`file`和`editor`，文档名称变化不改变命令、参数、API或返回状态。

常见组合：

- **日常AI开发，优先推荐**：文件读取 → 编辑器修改 → 按要求保存 → 完整回读 → 用户编译。写前实时身份和基线检查仍保留。
- **离线批量处理**：用户关闭工程 → 文件读写 → 用户重开工程、核对并编译。
- **纯分析**：优先文件查询；涉及未保存内容时读取编辑器。保护用户未保存内容，先解决基线差异再写入。

### 依赖和能力边界

需要Python3.9+，运行部分仅标准库。编辑器操作模式还需Windows PowerShell/.NET，以及同一交互桌面中已打开的AutoShop工程。原后台已验**Windows10 / AutoShop V4.11.0.5 / Python3.9.1**；不能据此宣称新电脑、Python3.12、Claude Code或全部客户端已验收。

支持已识别ST、ST正文型FB/FC、有界查询、限定变量/结构/GVT/实例操作、备份与受保护写入。新增[梯形图只读](references/ladder-reading.md)：文件模式读取LD程序/FB的网络、图元、连接、FB调用引脚、局部变量及内嵌ST，编辑器可读取普通图及已物化ST控件；默认scan仍仅识别LD，完整实时混合图未实现。**不发布梯形图写入或排序**。系统定义只读且需用户本机安装XML；不做硬件配置、PLC下载/启停/强制IO或自动编译。详细范围和验证程度见[能力表](references/capabilities.md)。

### 安装细节与客户端兼容性

| 客户端 | 项目级安装示例 |
| --- | --- |
| Codex／ChatGPT桌面中的Codex | 将本目录**完整放入**项目的 `.agents/skills/autoshop-bridge/`，在该项目打开会话并输入 `$autoshop-bridge`。 |
| 本机Windows上的Claude Code | 将本目录**完整放入**项目的 `.claude/skills/autoshop-bridge/`，在该项目启动Claude Code并输入 `/autoshop-bridge`；本包尚未在Claude Code实测。 |

SKILL.md、backend、参考文档和清单必须一起保留。上述路径分别属于对应客户端；本预览包没有提供普通ChatGPT／Claude网页聊天的本机AutoShop对接入口。可选全局安装由用户自行决定：当前Codex用户级目录是`~/.agents/skills/autoshop-bridge/`，Claude Code是`~/.claude/skills/autoshop-bridge/`，本Skill不自动安装或修改全局配置。

安装时使用可信的完整干净导出包和全新目录。含`.git/`的克隆目录、额外文件或Python缓存会被严格包检查拒绝，仓库元数据不能混入运行安装目录。失败时保留原安装，按[部署排错](references/environment.md#安装完整性失败)处理，不删除未知文件或改清单绕过。

Codex按当前工作目录及其仓库祖先路径发现Skill，不任意向下扫描子项目。未出现时先核对目录和完整布局，再开新会话或重启客户端。开发仓库的小型发现适配依赖本完整目录，不能单独复制。官方安装依据：[Codex](https://learn.chatgpt.com/docs/build-skills)、[Claude Code](https://code.claude.com/docs/en/skills)；安装路径有依据不等于本包已在该客户端验收。

### 目录、验收与排错

| 路径 | 用途 |
| --- | --- |
| SKILL.md | AI触发、决策与可靠流程 |
| references/ | 按需的正文/表操作、环境、故障和验收说明 |
| backend/ | 由唯一维护源导出的固定版本运行资源，不手工演进第二套实现 |
| scripts/check_bundle.py | 只读清单/哈希检查，不是数字签名 |
| examples/offline_smoke.py | 两个合成工程的CLI操作、搬移、备份与恢复验收 |
| bundle-manifest.json | 版本、源/导出文件哈希及脱敏记录 |

以本次加载的Skill绝对目录设置`$skill`，`$out`使用安装目录之外的全新绝对输出目录。逐条运行并检查结果：

```powershell
python -B "$skill/scripts/check_bundle.py"
python -B "$skill/examples/offline_smoke.py" --output $out
```

[两项目验收步骤](references/validation.md)区分离线、独立AI和真实IDE。冒烟只生成并修改合成样例，不打开AutoShop、不编译。独立AI已完成ST/FC任务；历史试用结果在包外开发记录维护，不混入AI日常操作说明。客户端自动发现和两真实工程IDE试验仍待验。写出、保存、回读、编译与设备行为分别记证。

失败时保留错误JSON、阶段和备份位置，先检查现状，再决定重试；不要保存旧窗口或假定自动回滚，详见[环境与恢复](references/environment.md)。本包不带开发机预编译缓存，grid使用既有PowerShell固定C#兼容入口；无常驻服务/MCP或统一进度、取消接口。

采用**B：可移植分发**，不依赖开发机绝对路径、客户工程或在线服务。允许清单和已知模式筛查排除真实工程、截图、厂商XML、个人路径及开发历史，但不保证发现所有语义敏感信息。GitHub仓库已公开，完整包随附[MIT许可证](LICENSE)；本包不包含AutoShop本体或厂商资料。

### 许可证

采用[MIT许可证](LICENSE)，版权署名2026 shaying526；AutoShop本体及厂商资料仍适用各自条款。

### 版本记录

s15补齐已识别非零折叠行字段的ST离线增删行。独立MAIN候选37→28行及增删行完整回读、编译0错误；未知字段给出具体行/字段/值，见[验收](references/validation.md)。

s14补齐严格空FBI编辑器首项/第二项及两模式删空。独立副本已保存、重开、完整回读，恢复后编译0错误；删空保留旧引用时的编译错误另列，见[验收说明](references/validation.md)。

s13将MIT许可证纳入完整包及校验清单，后台功能保持。

s12增加已有结构成员改名与必要原生初始化键同步；正文引用由调用者处理。

后台 **1.03** · Skill **2026-10-27.s15**。具体操作范围和验证证据见[能力表](references/capabilities.md)、[验收说明](references/validation.md)。

s11补齐FC两种模式的标量声明新增，包含空表首项/第二项。独立AutoShop副本已保存、重开、完整回读并全部编译0错误；初值必须null，文件模式保持完整正文及已有记录。

s10修复显式正文凭据路径的旧镜像误拒绝。HCP占用并未解除；使用关闭时直接快照、当前进程/树、全部冻结文件及干净目标正文共同核验，镜像差异仅作提示。保存后凭据仍失效，类型目录/变量新增/创建权限未放宽。独立副本捕获、打开、读取、修改保存和全文回读通过；本轮未编译。

s9修复结构成员注释中ASCII `=`的保守误拒绝，`#`原行为保持；独立副本的INOUT端口与全局结构变量已分别经真实界面保存、离线写入、完整回读和0错误编译。其他未验分隔符、非零未知ST行字段仍拒绝；不能据此推断整批请求均可执行。详见[离线编辑](references/offline-editing.md)。

