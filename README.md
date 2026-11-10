# AutoShop Bridge Agent Skill

## s34 本地修订

`2026-11-10.s34 / CLI 1.03` 增加关闭工程创建空白或带一行注释的 LiteST FB。含数组成员的 GVT 普通结构根沿既有离线流程使用 AutoShop 默认初值。见[离线编辑](references/offline-editing.md)。

## s33历史本地修订：FBI初值分页与显式成员路径

本地修订`2026-11-02.s33 / CLI1.03`：开发CLI支持工具箱初值完整稀疏分页、显式结构／FB祖先路径展开与限定标量叶编辑；公共service35签名及包外90案例保持，物理选择为显式opt-in。请求与边界见[数据编辑](references/data-editing.md)，实际阶段范围见[验证说明](references/validation.md)。最终软件与ZIP结果以包外真实回执为准；仅本地，不安装或远端发布。

## s32历史本地修订：FC已有类别与数值标量类型

本地修订`2026-11-01.s32 / CLI1.03`。FC已有声明可明确修改`category`或`data_type`：输入记录原生类型CString须为空，类型限BOOL／INT／DINT／REAL，原类别须已识别；新类别限VAR／IN／OUT／INOUT，新类型限上述四种。正常界面独立对照仅VAR→OUT、INT→REAL，其余组合仅合成检查。

文件与编辑器两模式的保存、跨会话完整六列／正文／原生回读已完成；组合编译于`2026-11-01 21:57:37`、恢复编译于`2026-11-01 22:13:13`各显示0错误／9588行。最终67份原件、独立59份源码及192文件集合和全部SHA均精确恢复，关闭观察与严格停止分别留证。FBI嵌套路径仅布局观察，尚未实现。

完整软件测试及ZIP最终结果只由随后包外真实回执提供；本段不预填测试总数、包数量或构建结论。不安装、不远端发布。请求与限制见[数据编辑](references/data-editing.md)，阶段范围见[验证说明](references/validation.md)。

## s31历史本地修订：FC普通结构与FB结构ARRAY递归默认

拟议修订`2026-11-01.s31 / CLI1.03`。本轮限定原生验收、完整持久回读、组合／恢复0错误编译、正常关闭观察及最终原件恢复完成。最终完整软件、资源数量、manifest及ZIP结果以随后包外真实交付回执为准；本段不预填这些数值。仅本地，不安装或远端发布。

FC普通已登记命名结构声明（code64），以及FB一／二维结构ARRAY中更深code64成员默认、含ARRAY成员子结构的默认表示。FC沿独立三尾记录，所有新增明确null，无FB式初值／保持字段；FB结构ARRAY沿独立value／comment模板，code64继续处理准确已识别子定义，code128成员省略并保留原位置分隔符，不生成其内部元素默认值。普通结构的根注释模板仍独立，GVT／STRU普通根不是这种默认生成。

准确非空定义、真实选择器、全部可读定义哈希、未保存内容、唯一备份、CAS及旧记录／正文／不透明字节和完整回读保护保持。FC／GVT／STRU普通根只核准确身份，不递归证明成员业务合法性；FB只遍历实际code64默认依赖，省略的ARRAY不追业务元素图。FB递归格式以工作栈、活动类型路径及共享UTF-8预算实现；循环、错名／缺失／空定义、未知标量或注释语法拒绝。嵌套空注释关闭后不加07，标量空注释仍保留07；预算沿现有65533字节CString／容器边界，不是PLC容量规则。helper缺省及既有非递归模式、sharedflat和结构改名不扩。三维、IEC上下界、FB元素ARRAY、任意显式复杂初值、ARRAY成员内部元素默认构造、未知宿主记录、FC返回类型／FCI／FC中FB实例／通用新建FC仍另待。

FC与FB均沿既有offline及editor-variables入口，明确`initial_value:null`。例如准确登记非空结构`NodeData`可用作FC普通根，`NodeData[2]`或`NodeData[2,2]`可用作FB结构ARRAY；类型存在性、原生身份与全部依赖字节须准确冻结，不把示例当默认工程。FC没有初值／保持列；FB普通结构根注释默认与ARRAY子值默认分开。

正常FC三条VAR与FB八条ARRAY有独立完整wire／手写默认对照，正式两模式空／非空及四类别另行留证。本次组合编译FCI伴随不透明三字节变化按精确前后原像单例审查并最终恢复，未将它解释为地址或增加FCI编辑能力。辅助脚本派发前失败、严格释放HCP停止与另行独立原像审查／45秒续作保留各自证据，不反写旧阶段为通过。空表声明区折叠时公共几何保护仍停止；正常展开布局并完整重读后另阶段续作，不忽略guard或宣称Computer Use恢复。UI隐藏值、显示预览与原生默认分别保留；公共签名与权限边界保持。详见[分阶段验证](references/validation.md)。

[English](#english) | [简体中文](#简体中文)

## English

Previous s30 native-gate record (historical) **2026-11-01.s30 / CLI 1.03** adds ordinary registered named members in existing nonempty STRU tables and ordinary GVT references to registered structures containing ARRAY or nested members. STRU native coverage is nonempty only in both modes; GVT covers empty/nonempty tables in both modes. STRU members have no initializer/category/address fields; GVT additions require JSON null and retain the observed empty native initializer. These are exact-root references, separate from FB default expansion; no recursive business-dependency proof is required. Definition freezing, old-record/body/opaque-byte preservation, unique backups, complete readback and project CAS remain required. Scoped native acceptance and final restoration are complete: original67, independent59 sources and all192 file hashes equal the batch baseline. At this native-gate checkpoint, final full software regression and packaging had not started; actual build, manifest and ZIP results belong to the later external receipt. No installation or remote release is included. See [staged validation](references/validation.md).

The original combination trial reported one real compiler error for four missing global `::` prefixes. Its failed capture remains preserved. A bounded source correction and a separate compile at **2026-11-01 15:41:37** reported **0 errors / 9596 lines**; a separate recovery compile at **2026-11-01 16:28:23** reported **0 errors / 9588 lines**. Scoped native acceptance and restoration are complete; final software and ZIP gates remain separate.

Historical local s29 scope **2026-11-01.s29 / CLI 1.03 / 91 files** adds bounded FB defaults in all four categories, with explicit JSON null initializers. Ordinary structure defaults retain root comment slots for identified nested-structure and ARRAY members without generating their values. One/two-dimensional ARRAYs of nested structures use a separate value/comment template, expanding exactly one nested level whose frozen child definition is an observed flat-scalar profile. Deeper nesting, ARRAY children, unknown descriptors/defaults and explicit complex initializers require separate evidence. GVT ordinary structures, direct named STRU additions and structure-renaming eligibility keep their prior strict scope. Native text and hidden UI previews remain separate observations. Actual construction and native/software/ZIP verification belong to the external receipt; no installation or remote release is included. Installed/public s24 and historical s28 evidence remain separate. The source contract and synthetic inventory/fingerprint remain outside the portable package; public signatures stay at 35.

Nested-default assembly uses a UTF-8 byte budget bounded by the existing writer's 65,533-byte CString ceiling and native-container limit. Dimension wrappers are reserved before root/child appends; oversized output is rejected before a large intermediate string is built. These are existing file-format/memory bounds, without a new PLC-capacity or member-count policy.

Historical local s28 scope **2026-10-31.s28 / CLI 1.03** adds bounded default construction for one/two-dimensional FB ARRAYs of registered flat structures containing BYTE/IP scalar members, plus observed special member comments in ordinary/ARRAY templates. Both modes cover all four FB categories with explicit JSON null initializers. Native raw values, hidden UI text and previews remain separate observations. Nested defaults, three dimensions, explicit bounds, FB elements and explicit complex initializers remain outside scope. Exact native/software/compilation results belong to this batch's external receipt. This is local only; installed/public s24 and original s27/s26/s25 evidence remain separate. Source contract r39 and its actual synthetic inventory/fingerprint stay outside the portable package; public signatures remain 35.

Historical local s27 scope **2026-10-31.s27 / CLI 1.03** adds one/two-dimensional BYTE and IP ARRAYs in both modes for FB, FC, structure members and GVT, plus ordinary references to registered flat structures containing BYTE/IP members in all four FB categories and GVT. These additions use explicit JSON null initializers; structure members have no category/initializer fields, and FC has no native initializer. New scalar-member defaults inside structure ARRAYs, unknown nested defaults, three dimensions, explicit bounds and FB elements remain outside this scope. EtherNet/IP exported tags can impose additional type constraints; AutoShop compilation checks engineering semantics, without changing network configuration. Native/software/compilation results belong to the final external receipt. This is local only, with no installation or remote release. Source contract r38 (77 synthetic cases, 35 signatures) stays outside the portable package; s26/s25 evidence retains its original scope.

Historical local s26 scope **2026-10-31.s26 / CLI 1.03** adds direct BYTE/IP declarations in both modes for FB, FC, structure members and global tables. FB supports all four categories; initializers are explicit strings for FB VAR/IN/OUT and GVT, JSON null for FB INOUT and FC, and absent for structure members. Defaults are BYTE `0` and IP `192.168.1.0`; GVT displays 8/32 bits. BYTE/IP ARRAYs and unobserved complex-default construction remain unsupported. Scoped native acceptance and final software results belong in this batch’s receipt outside the package. This is a local candidate, with no installation or remote release; completed s25 evidence and installed/public s24 remain separate. Source contract r37 (73 cases, 35 signatures) is not shipped in the portable package.

FB ARRAY comment display and append/save readback follow the observed IDE representation while preserving raw snapshots. Other hosts and unknown encodings retain their existing boundaries.

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

Scoped native acceptance is complete for s25 ARRAY additions in both modes and associated FB structure-array initializer-key renames. Full readback, separate backend/normal-UI controls and the final restored baseline passed zero-error compilation and guarded close observation on Windows 10 / AutoShop V4.11.0.5. Final software verification results belong in this delivery's receipt outside the package; these controls do not establish the cause or repair of historical control faults. See [staged validation](references/validation.md).

Edit existing FBI instance names, comments and initial values in either mode. Editor Mode also adds library and registered LD FB instances; both modes support mixed structure member comments. File edits preserve references for the caller; IDE renames report AutoShop's actual reference changes. See [usage](references/data-editing.md#fbi已有实例编辑) and [validation](references/validation.md).

s18 adds offline global FBI instances of registered project FBs, including first declarations and batch appends in qualified containers. AI supplies body/reference edits; see [validation](references/validation.md).

s17 adds offline internal project-FB instances, including first declarations and batch appends. AI supplies body/reference edits; native defaults and existing records stay protected. See [validation](references/validation.md).

s16 adds scalar and supported structure declarations to recognized empty GVT tables in both modes, including a second structure without an existing scalar probe. See [validation](references/validation.md).

s15 adds offline ST edits with observed nonzero fold metadata, including line insertion and deletion. An independent 37-to-28-line MAIN candidate passed full readback and zero-error compilation; see [validation](references/validation.md).

s14 adds editor first/second instances in recognized empty FBI tables and deletion to the observed empty profile in both modes. Save/reopen/full-readback and restoration compilation were verified in an independent copy; see [validation](references/validation.md).

s13 includes the MIT license in the complete package and integrity manifest; backend behavior is unchanged.

s12 adds existing structure member renames with associated native initializer-key updates. Source references remain under the caller’s control.

Backend **1.03** · Historical local Skill **2026-10-31.s28**; scoped native acceptance and final software results are established by this batch’s external receipt. The following s25 entries retain their historical scope. Final software verification results are recorded in this delivery's receipt outside the package; the manifest and `check_bundle` establish the actual resource inventory and integrity. Installed/public distribution remains **2026-10-30.s24 / 89 files**. This delivery is local only, with no installation or remote release. Detailed limits and evidence: [capabilities](references/capabilities.md), [validation](references/validation.md). The other entries in this section record earlier revisions.

s11 adds scalar FC declarations in both modes, including the first variables of an empty table. Independent AutoShop copies passed save/reopen/full-readback and zero-error compilation. FC additions require `initial_value: null`; offline edits preserve the complete body and existing records.

s10 fixes stale-mirror rejection in the explicit body registration-receipt route. A locked HCP is still unreadable; the existing target is checked using the closed direct-HCP snapshot, live process/tree, all frozen files and clean editor content. Mirror differences remain advisory. Saving still invalidates the receipt. Independent-copy capture/open/read/edit/save/full-readback passed; no compilation was requested or performed in this fix.

s9 fixes a conservative rejection of literal `=` in structure-member comments. Independent AutoShop V4.11.0.5 copies verified INOUT ports and structured globals through IDE saves, offline writes, full readback and zero-error compilation. Other unobserved delimiters and nonzero unknown ST row fields remain rejected; a multi-target request can still be blocked elsewhere. See [offline editing](references/offline-editing.md).

## 简体中文

## s30历史本地候选：STRU命名成员与GVT普通结构引用（限定原生验收与恢复已完成）

拟议修订为`2026-11-01.s30 / CLI1.03`。三项限定原生验收、跨会话完整回读、恢复编译及最终恢复已完成：67份原件、独立59份源码和192文件集合／全部SHA均与本批基线一致；各本轮正常关闭45秒存活及精确进程事件分别留证。本段记录原生门禁完成时的状态：最终完整软件回归尚未开始，尚未构建本批包；资源数量、manifest及ZIP须由随后实际构建和包外最终回执确认，不以历史测试数或旧包清单代替。不安装、不远端发布，已安装／公开记录仍分开。范围与阶段见[分阶段验证](references/validation.md)。

新增范围分为三项：已有非空STRU中新增准确登记的普通命名结构成员；GVT新增含ARRAY成员结构的普通根引用；GVT新增含嵌套结构成员结构的普通根引用。STRU的两模式原生证据限已有非空结构，不提供空STRU容器构造或首成员新增资格；GVT覆盖两模式空／非空表。这里写入普通根类型记录，不展开子成员默认值，不沿业务依赖图递归证明类型或引用正确；FB中既有一层嵌套ARRAY默认构造仍是独立profile，不能混同为GVT／STRU初始化语法。

STRU新增仅有`op/name/data_type/comment`，没有`category/initial_value`、保持或地址字段；GVT结构新增必须显式`initial_value:null`，已观察保存原生初值为空。准确非空根定义、类型code/text和真实选择器核对、可读定义哈希冻结、原记录／正文／不透明字节、未保存内容、唯一备份、全工程并发CAS与完整原生／实际UI回读保护保持。GVT展开监视行与根声明分别读取；`...`预览不代替初值。工具不生成／复制地址，不添加CSV写入器，也不扩大结构改名、FC返回类型、深层默认、子ARRAY展开、三维／显式上下界或任意显式复杂初值范围。

首次组合验证真实编译有1错误：验证正文四处全局变量引用缺少`::`。原失败及其生成物缺失状态保留；限定修正正文后另一次编译在`2026-11-01 15:41:37`显示0错误、9596行。新结果不把首次失败改为通过，恢复编译另于`2026-11-01 16:28:23`显示0错误、9588行；限定原生及最终67／59／192恢复核对已完成，最终完整软件回归与ZIP仍另验。本地未安装、未远端发布；已安装／公开记录仍与本地候选分开。

以下s29及更早段落保留历史范围；当前三项普通引用资格仅由本节细化，不把旧FB默认展开或历史通过移作本批完整验收。

## s28历史本地候选：FB结构ARRAY默认与特殊成员注释

s28历史本地候选为`2026-10-31.s28 / CLI1.03`，本批范围为含BYTE/IP标量成员的已登记扁平结构在FB一/二维ARRAY中的默认构造，以及已观察结构成员特殊注释在普通/ARRAY初始化模板中的保留。两模式沿现有入口覆盖VAR/IN/OUT/INOUT，新增统一传`initial_value:null`；默认由限定原生profile生成，不由调用者拼接复杂初值。具体原生、软件验证和编译结果以包外本批最终回执为准；不安装、不远端发布，实际安装/公开仍s24。本地s27/s26/s25及原失败证据保持原范围。

定义内BYTE/IP直接成员继续没有category或initial_value字段。要求准确登记、根定义哈希冻结及各成员布局完整识别；身份、未保存内容、并发、唯一备份、旧记录/正文/不透明字节、完整原生及实际UI回读保护保持。普通结构的UI隐藏初值与原生全文可能不同，ARRAY在本批profile中另行核对，不能把隐藏栏或`...`预览当作原生串。

未知嵌套默认、三维、显式上下界、FB元素、任意显式复杂初值、未知控制字符及其他宿主新默认语法不扩张。EtherNet/IP导出等工程语义交AutoShop编译检查，不自动修改网络配置或推算地址。源码契约1.2.0/r39及合成示例在包外维护；实际案例数和代码指纹以源码契约JSON为准，35个公共签名保持，合成验证不等于原生验收。

以下s27及更早章节是历史范围；旧限制仅由本节明确新增范围细化，旧成功不改标签为s28。

FB ARRAY注释显示及新增保存回读已按正常IDE表示核验，原生快照保持原串；其他宿主及未知编码边界保持。

s27历史本地候选为`2026-10-31.s27 / CLI1.03`，仅本地校验，不安装或远端发布；s26/s25原交付及验证记录保留，实际安装/公开仍s24。具体原生、软件验证和编译结果以包外本批最终回执为准，资源数量与完整性以实际manifest和check_bundle为准。

两种模式支持BYTE与IP元素的一/二维ARRAY，在LiteST FB、FC、STRU直接成员及GVT分别沿各宿主独立profile执行；例如`BYTE[2]`、`BYTE[2,3]`、`IP[2]`、`IP[2,3]`。另支持准确登记、含BYTE/IP成员的扁平结构普通引用：FB VAR/IN/OUT/INOUT与GVT。继承s26直接标量及s25既有ARRAY范围，不重复把旧能力列为本批新实现。新ARRAY和普通结构引用均明确`initial_value:null`；STRU成员仅op/name/data_type/comment，没有category或initial_value。FC保留独立三尾字段且没有原生初值，不由此开放FC普通结构引用。FB数值ARRAY和GVT ARRAY沿已观察空原生默认，普通结构FB注释默认与GVT空原生默认分开核对；实际隐藏值、预览及原生串各自完整读取，不从位长、预览或标量IP默认值推算数组布局。含BYTE/IP标量成员的结构ARRAY默认构造、未知nested默认、三维、显式上下界、FB元素ARRAY及任意显式复杂初始化不由本批开放。保留准确类型/登记、定义哈希、未保存状态、并发、唯一备份、原记录/正文/不透明字节、完整回读和非目标保护；写出、保存、重开回读及编译分别记证。EtherNet/IP导出标签等工程配置对成员类型另有语义限制，声明格式受支持不等于所有网络对象均可编译；语义交AutoShop编译检查，不自动更改业务网络配置，也不通过猜地址、改UI映像或修改缓存绕过完整回读。源码契约1.2.0/r38、77合成案例/35公共签名在包外维护，不在portable包内；合成验证不代替原生保存、持久回读或编译验收。

以下s26/s25及更早内容保留各自历史范围；旧限制仅由上述明确新范围细化，旧成功不追认为s27成功。

s26历史本地修订为`2026-10-31.s26 / CLI1.03`，不安装、不云端发布；本地s25已完成并保留历史证据，实际安装/公开仍为s24。具体原生、软件验证和编译结果以包外本批回执为准，资源数量与完整性以实际manifest和check_bundle为准。

两模式支持FB四类别、FC、STRU直接成员及GVT的BYTE/IP新增。BYTE原生类型码8192、IP4096，IDE默认分别为`0`和`192.168.1.0`；GVT位长8/32。FB VAR/IN/OUT及GVT用明确字符串初值，FB INOUT及全部FC用JSON null；FC没有原生独立初值字段，STRU直接成员没有category/initial_value。IP沿已观察ATL文本控件写入并完整回读原文，不转换为推算地址。共享descriptor不开放BYTE/IP ARRAY或含这些成员结构的默认构造，未知复杂默认串仍准确报告未实现。源码契约r37/73案例/35签名不随portable包交付。

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

s25两模式已识别ARRAY新增及FB结构数组默认成员键关联改名的限定原生验收完成：完整回读、后台/正常界面对照及最终恢复基线分别编译0错误，关闭观察与事件审计通过。最终软件校验结果以本次包外交付回执为准，不能由新对照推定历史控件故障根因已修。适用本机Windows10 / AutoShop V4.11.0.5，详见[分阶段验证](references/validation.md)。

两种模式可编辑FBI已有实例的名称、注释和初值；编辑器模式可新增库及已登记LD类型实例，扁平结构支持混合空/非空成员注释。文件模式由调用者处理引用，编辑器模式记录IDE实际引用更新；见[用法](references/data-editing.md#fbi已有实例编辑)和[验收](references/validation.md)。

s18补齐方法一全局FBI项目FB实例的空表首项和批量追加，保留已有记录、容器和未分配地址保护；正文由AI组织，见[验收](references/validation.md)。

s17补齐方法一内部项目FB实例的空表首项和批量新增。正文/引用由AI组织，工具准确生成原生默认记录并保护旧记录，见[验收](references/validation.md)。

s16补齐严格空GVT两模式的标量/结构首项及后续追加，仅结构表也可继续新增。实际保存、重开、完整回读与编译证据见[验收](references/validation.md)。

s15补齐已识别非零折叠行字段的ST离线增删行。独立MAIN候选37→28行及增删行完整回读、编译0错误；未知字段给出具体行/字段/值，见[验收](references/validation.md)。

s14补齐严格空FBI编辑器首项/第二项及两模式删空。独立副本已保存、重开、完整回读，恢复后编译0错误；删空保留旧引用时的编译错误另列，见[验收说明](references/validation.md)。

s13将MIT许可证纳入完整包及校验清单，后台功能保持。

s12增加已有结构成员改名与必要原生初始化键同步；正文引用由调用者处理。

后台 **1.03** · s28历史本地Skill **2026-10-31.s28**，限定原生验收及最终软件结果见包外本批回执；以下s25记录保持各自历史范围；最终软件校验结果以本次包外交付回执为准，资源数量及完整性以实际manifest和`check_bundle`为准。实际安装/公开仍为 **2026-10-30.s24 / 89文件**，本轮仅本地交付，不安装、不远端发布。具体范围和证据见[能力表](references/capabilities.md)、[验收说明](references/validation.md)；本节其他条目保留前版历史。

s11补齐FC两种模式的标量声明新增，包含空表首项/第二项。独立AutoShop副本已保存、重开、完整回读并全部编译0错误；初值必须null，文件模式保持完整正文及已有记录。

s10修复显式正文凭据路径的旧镜像误拒绝。HCP占用并未解除；使用关闭时直接快照、当前进程/树、全部冻结文件及干净目标正文共同核验，镜像差异仅作提示。保存后凭据仍失效，类型目录/变量新增/创建权限未放宽。独立副本捕获、打开、读取、修改保存和全文回读通过；本轮未编译。

s9修复结构成员注释中ASCII `=`的保守误拒绝，`#`原行为保持；独立副本的INOUT端口与全局结构变量已分别经真实界面保存、离线写入、完整回读和0错误编译。其他未验分隔符、非零未知ST行字段仍拒绝；不能据此推断整批请求均可执行。详见[离线编辑](references/offline-editing.md)。

