---
name: autoshop-bridge
description: Read and modify AutoShop PLC projects using bundled scripts. Use for ST program bodies, ST-backed FB/FC, supported variables and structures, project queries, backups, editor synchronization and experimental read-only LD programs/FBs. Not for generic Python development, ladder editing, hardware configuration or PLC download/control.
---

## s34 关闭工程创建 LiteST FB 和结构变量

`offline-fb-plan` 预检空白或单行注释 LiteST FB，`offline-fb-create` 用计划摘要和唯一备份写入原生 FB、树目录与 HCP。先保存并关闭整个工程。含数组成员的已登记结构可通过 `offline-*` 新增 GVT 普通根，传 `initial_value:null`，地址由 AutoShop 分配。命令、适用布局及失败回执见[离线编辑](references/offline-editing.md)。

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

# AutoShop Bridge

## s30历史本地候选：STRU命名成员与GVT普通结构引用（限定原生验收与恢复已完成）

拟议修订为`2026-11-01.s30 / CLI1.03`。三项限定原生验收、跨会话完整回读、恢复编译及最终恢复已完成：67份原件、独立59份源码和192文件集合／全部SHA均与本批基线一致；各本轮正常关闭45秒存活及精确进程事件分别留证。本段记录原生门禁完成时的状态：最终完整软件回归尚未开始，尚未构建本批包；资源数量、manifest及ZIP须由随后实际构建和包外最终回执确认，不以历史测试数或旧包清单代替。不安装、不远端发布，已安装／公开记录仍分开。范围与阶段见[分阶段验证](references/validation.md)。

新增范围分为三项：已有非空STRU中新增准确登记的普通命名结构成员；GVT新增含ARRAY成员结构的普通根引用；GVT新增含嵌套结构成员结构的普通根引用。STRU的两模式原生证据限已有非空结构，不提供空STRU容器构造或首成员新增资格；GVT覆盖两模式空／非空表。这里写入普通根类型记录，不展开子成员默认值，不沿业务依赖图递归证明类型或引用正确；FB中既有一层嵌套ARRAY默认构造仍是独立profile，不能混同为GVT／STRU初始化语法。

STRU新增仅有`op/name/data_type/comment`，没有`category/initial_value`、保持或地址字段；GVT结构新增必须显式`initial_value:null`，已观察保存原生初值为空。准确非空根定义、类型code/text和真实选择器核对、可读定义哈希冻结、原记录／正文／不透明字节、未保存内容、唯一备份、全工程并发CAS与完整原生／实际UI回读保护保持。GVT展开监视行与根声明分别读取；`...`预览不代替初值。工具不生成／复制地址，不添加CSV写入器，也不扩大结构改名、FC返回类型、深层默认、子ARRAY展开、三维／显式上下界或任意显式复杂初值范围。

首次组合验证真实编译有1错误：验证正文四处全局变量引用缺少`::`。原失败及其生成物缺失状态保留；限定修正正文后另一次编译在`2026-11-01 15:41:37`显示0错误、9596行。新结果不把首次失败改为通过，恢复编译另于`2026-11-01 16:28:23`显示0错误、9588行；限定原生及最终67／59／192恢复核对已完成，最终完整软件回归与ZIP仍另验。本地未安装、未远端发布；已安装／公开记录仍与本地候选分开。

以下s29及更早段落保留历史范围；当前三项普通引用资格仅由本节细化，不把旧FB默认展开或历史通过移作本批完整验收。

## s29历史本地范围：FB嵌套结构及含ARRAY成员结构默认

本批拟交付`2026-11-01.s29 / CLI1.03 / 91文件`，实际构建、原生验收、软件回归及ZIP状态以包外本批最终回执为准。仅本地，不安装或远端发布；安装/公开此前记录仍s24，s28及更早交付、失败和恢复证据保持各自原范围。

限定LiteST FB VAR/IN/OUT/INOUT，两模式空/非空新增沿既有入口，均显式`initial_value:null`。普通结构新增使用根成员comment模板：准确识别的nested结构成员(code64)及ARRAY成员(code128)有非空原生注释时保留`成员:=`、原生07分隔及原comment；不生成其值、不递归业务依赖。成员按根定义原序，分隔符保持已观察的原位置规则，全部注释为空则默认空串。

嵌套结构的一/二维ARRAY采用独立value/comment模板，仅展开一层nested成员，其child必须为准确已登记且已冻结的已验flat scalar定义。child逐成员输出已知默认值、原生07及原comment，再接根成员07及原comment；不是普通结构的comment-only模板。更深nested、ARRAY child、未知描述及默认、显式复杂初值、三维/IEC上下界、FB元素ARRAY仍需独立实现和证据，不凭本批扩大。

组装nested默认串时按UTF-8字节使用既有writer的65533字节CString上限与原生容器上限的较小值，预留维度包装并在根/child追加前检查预算；越界早拒，不先构造超大中间串。这是既有文件格式及内存边界，不增加PLC容量、成员数或业务规模限制。

这两种默认profile只由FB新增路径显式启用。GVT普通结构新增、STRU普通命名成员新增和结构改名等既有strict资格保持；不把FB默认语法套到其他宿主。准确原生code/text、定义和身份冻结、未保存内容、并发、唯一备份、旧记录/正文/不透明字节及完整原生/实际UI回读继续保护；语义由AutoShop编译检查，不修改网络配置或推算地址。

普通结构UI隐藏初值可能大写、排序，与native全文分开记录；本批nested ARRAY的hidden等于native仅为所观察profile，不推广到所有复杂类型。源码契约、合成案例及实际指纹在包外维护，公共签名35个保持；合成测试、正常保存oracle、两模式持久回读、组合/恢复编译及关闭观察分别计证。以下s28及更早章节仅保留历史范围，旧限制只由本节明确新增部分细化。

## s28历史本地候选：FB结构ARRAY默认与特殊成员注释

s28历史本地候选为`2026-10-31.s28 / CLI1.03`，本批范围为含BYTE/IP标量成员的已登记扁平结构在FB一/二维ARRAY中的默认构造，以及已观察结构成员特殊注释在普通/ARRAY初始化模板中的保留。两模式沿现有入口覆盖VAR/IN/OUT/INOUT，新增统一传`initial_value:null`；默认由限定原生profile生成，不由调用者拼接复杂初值。具体原生、软件验证和编译结果以包外本批最终回执为准；不安装、不远端发布，实际安装/公开仍s24。本地s27/s26/s25及原失败证据保持原范围。

定义内BYTE/IP直接成员继续没有category或initial_value字段。要求准确登记、根定义哈希冻结及各成员布局完整识别；身份、未保存内容、并发、唯一备份、旧记录/正文/不透明字节、完整原生及实际UI回读保护保持。普通结构的UI隐藏初值与原生全文可能不同，ARRAY在本批profile中另行核对，不能把隐藏栏或`...`预览当作原生串。

未知嵌套默认、三维、显式上下界、FB元素、任意显式复杂初值、未知控制字符及其他宿主新默认语法不扩张。EtherNet/IP导出等工程语义交AutoShop编译检查，不自动修改网络配置或推算地址。源码契约1.2.0/r39及合成示例在包外维护；实际案例数和代码指纹以源码契约JSON为准，35个公共签名保持，合成验证不等于原生验收。

以下s27及更早章节是历史范围；旧限制仅由本节明确新增范围细化，旧成功不改标签为s28。

工具是工程编辑的执行层：AI负责语法、声明、引用和业务语义，AutoShop编译检查结果。正常创建、删除、修改不要求先证明业务正确，不额外增加人工审批；身份、未保存内容、并发、格式、唯一备份及完整回读用于保证执行准确。未实现字段应如实说明并走已实现路径，不能把旧白名单当永久禁止。

s27历史本地候选为`2026-10-31.s27 / CLI1.03`，仅本地校验，不安装或远端发布；s26/s25原交付及验证记录保留，实际安装/公开仍s24。具体原生、软件验证和编译结果以包外本批最终回执为准，资源数量与完整性以实际manifest和check_bundle为准。两种模式支持BYTE与IP元素的一/二维ARRAY，在LiteST FB、FC、STRU直接成员及GVT分别沿各宿主独立profile执行；例如`BYTE[2]`、`BYTE[2,3]`、`IP[2]`、`IP[2,3]`。另支持准确登记、含BYTE/IP成员的扁平结构普通引用：FB VAR/IN/OUT/INOUT与GVT。继承s26直接标量及s25既有ARRAY范围，不重复把旧能力列为本批新实现。新ARRAY和普通结构引用均明确`initial_value:null`；STRU成员仅op/name/data_type/comment，没有category或initial_value。FC保留独立三尾字段且没有原生初值，不由此开放FC普通结构引用。FB数值ARRAY和GVT ARRAY沿已观察空原生默认，普通结构FB注释默认与GVT空原生默认分开核对；实际隐藏值、预览及原生串各自完整读取，不从位长、预览或标量IP默认值推算数组布局。含BYTE/IP标量成员的结构ARRAY默认构造、未知nested默认、三维、显式上下界、FB元素ARRAY及任意显式复杂初始化不由本批开放。保留准确类型/登记、定义哈希、未保存状态、并发、唯一备份、原记录/正文/不透明字节、完整回读和非目标保护；写出、保存、重开回读及编译分别记证。EtherNet/IP导出标签等工程配置对成员类型另有语义限制，声明格式受支持不等于所有网络对象均可编译；语义交AutoShop编译检查，不自动更改业务网络配置，也不通过猜地址、改UI映像或修改缓存绕过完整回读。源码契约1.2.0/r38、77合成案例/35公共签名在包外维护，不在portable包内；合成验证不代替原生保存、持久回读或编译验收。调用见[变量和表](references/data-editing.md)，边界见[能力表](references/capabilities.md)与[验证](references/validation.md)。

以下s26/s25及更早内容保留各自历史范围；旧限制仅由上述明确新范围细化，旧成功不追认为s27成功。

FB ARRAY注释读取显示及新增保存回读按正常IDE已观察的转义核对，原生快照保留原串；编辑器请求使用实际可见注释，不清洗或改写raw字段。此范围不推定其他宿主或未知控制字符，详见[变量和表](references/data-editing.md)。

s26历史本地修订`2026-10-31.s26 / CLI1.03`补齐BYTE/IP四宿主两模式直接新增，FB支持VAR/IN/OUT/INOUT。BYTE原生类型码8192、IP4096，IDE默认分别为`0`和`192.168.1.0`；GVT位长8/32。FB VAR/IN/OUT及GVT用明确字符串初值，FB INOUT及全部FC用JSON null；FC没有原生独立初值字段，STRU直接成员没有category/initial_value。IP沿已观察ATL文本控件写入并完整回读原文，不转换为推算地址。共享descriptor不开放BYTE/IP ARRAY或含这些成员结构的默认构造，未知复杂默认串仍准确报告未实现。具体原生、软件验证和编译结果以包外本批回执为准；本地候选不安装或更新云端，已完成s25及实际安装/公开s24保持。调用见[变量和表](references/data-editing.md)，阶段边界见[验证](references/validation.md)。源码契约r37/73案例/35签名由源码文档维护，不在portable包内。

s25历史本地修订`2026-10-31.s25 / CLI1.03`，ARRAY限定原生验收已完成；最终软件校验结果以本次包外交付回执为准，资源数量及完整性以实际manifest和check_bundle为准。实际安装/公开仍s24，本轮不安装或更新云端。沿既有offline、editor-variables与table-editor-edit使用准确`INT[3]`、`INT[3,2]`、`STRING<20>[2,3]`及已登记结构`TypeName[2]`等文本；默认初值为null，结构成员不带类别/初值。四宿主16组正常保存配对、42条新增记录已整文件exact，两模式空/非空保存及完整持久回读已有证据；限定新后台、正常界面及最终恢复分别编译0错误、关工程并通过45秒/事件审计，67原件/59源码已恢复核对。GVT原公共9项批超时与限定续作仍分开记录，历史vsflex/MFC故障不抹去，不宣称根因已修。调用及本机适用范围见[ARRAY开发调用](references/data-editing.md#array新增开发)与[分阶段证据](references/validation.md)。旧安装不能通过修改清单取得这些能力。

结构成员正规改名按[改名工作流](references/structure-renaming.md)：table-check支持field=name；table-apply或structure-rename-plan/apply同步已知关联初始化成员键。正文引用由调用者另行修改，旧引用不阻断改名。

FBI已有实例的名称、注释和初值走[既有实例编辑](references/data-editing.md#fbi已有实例编辑)：文件模式修改完整原生字符串；编辑器初值明确指定工具箱成员路径，先读取真实成员旧值。文件模式不改引用，正常IDE改名可能自动保存引用，按结果清单核对。

s24沿既有命令新增含REAL、`STRING<20>`/`STRING<128>`成员的已登记扁平结构变量及FB VAR/IN/OUT/INOUT接口，两模式结构新增均显式`initial_value:null`；FB默认模板与GVT空原生初值分开处理，不把隐藏预览当原生串。原生成员注释中已观察的6/8分隔符及CRLF保留，未知初始化语法明确诊断，不清零或删注释绕过。直接REAL/STRING声明的s23已交付；裸STRING默认128，容量识别不证明所有容量均已实测。JSON、调用和边界见[变量和表](references/data-editing.md)。未知HCPP显式资格走[项目登记基线](references/project-registration.md)，关闭工程批量写入见[离线开发](references/offline-editing.md)。本轮实测和未实现范围分别见[验证](references/validation.md)和[能力边界](references/capabilities.md)，历史成功不替代调用者本次验收。

以随包固定版本的CLI处理用户指定的AutoShop工程。只调用工具；不要修改后台Python/C#、生成的清单或备份。Skill不增加授权，也不绕过宿主限制。

说明中的**文件直改模式（方法一，Direct File Mode）**对应程序标识`file`，直接读写磁盘原生文件；**编辑器操作模式（方法二，Editor Mode）**对应`editor`，操作AutoShop编辑器缓冲并显式保存。这里只统一说明名称，不改命令、参数、API或结果状态。

## 先取得输入并检查环境

明确工程绝对目录、目标对象/功能、验收条件、文件直改或编辑器操作模式，以及是否保存。遵守目标工程自己的规则；不默认选择最近打开的工程或自行复制客户工程。只读任务无需询问保存意图。

从**本次加载的SKILL.md绝对路径**取得其父目录作为`$skill`，不要使用当前工作目录猜测。下列变量由本次任务提供，全部使用绝对路径：

- `$skill`：本Skill安装目录。
- `$project`：目标AutoShop工程目录，和Skill安装目录无关。
- `$artifacts`：用户选定的独立输出目录，位于Skill和原生程序目录之外；每次工作目录/结果文件用新名称。

```powershell
$bridge = Join-Path $skill 'backend/autoshop_bridge_cli.py'
python -B "$skill/scripts/check_bundle.py"
python -B $bridge --version
python -B $bridge --help
python -B $bridge project-summary --project $project --limit 20
```

实际调用须核对CLI `1.03`及本次安装包manifest中的skill_revision；本页s31原生关口完成不等于已安装升级；完整包结果以实际manifest及包外回执为准。历史s28及其实际manifest仍可独立核对；完整性检查应为`bundle_verified`，软件校验结果另见本次包外交付回执。实际安装/公开s24的修订仍为`2026-10-30.s24`；只看CLI版本不能证明已更新，也不能用旧清单证明s28完整性。`bundle_invalid`时停止工程调用，按[环境和限制](references/environment.md#安装完整性失败)定位部署问题。安装目录额外的`.git`或缓存也会被拒绝，不能删除未知文件或改清单绕过。Python要求3.9+标准库；方法二还需要Windows交互桌面、Windows PowerShell/.NET和已打开的目标AutoShop工程。不要自行启动服务、构建辅助程序或修改全局环境。

## 最短可靠流程

1. 先有界工程摘要；需要定义/引用时用`code-context`，按需导出和读片段，避免把整工程或窗口整表倾倒到上下文。已保存内容优先文件读取，磁盘不包含未保存缓冲。
   梯形图程序/FB读取改走[梯形图只读](references/ladder-reading.md)的随包独立脚本；已知文件绝对路径可直接读，不依赖HCP。先摘要，再分页读指定网络、引脚、连接和FB变量；不要用ST导出器或把默认scan的“仅识别”误当新读取入口。LD写入/排序仍未发布。
2. 选择模式。工程已关闭，需要正文增删行、空FB首变量、内部/全局FB实例、GVT结构根声明或已有非空STRU命名结构成员时，读[离线开发](references/offline-editing.md)，使用独立offline系列；方法一库/LD示例另见[变量和表](references/data-editing.md)，先核对本包版本。不要沿用旧build/apply的同LF限制或放宽未知行字段。方法二通过编辑器修改，可自动打开/切换目标标签；默认只改缓冲，显式`--save`才保存。不要先文件写入再用旧窗口/旧基线同步。
3. 正文任务按[正文编辑](references/source-editing.md)导出、核对基线、制作唯一原文补丁、预检并调用既有写入器。变量/表/实例新增修改改读[变量和表](references/data-editing.md)；明确删除改读[声明删除](references/declaration-editing.md)，使用独立declarations-read/editor-declarations-delete或offline入口，不向旧清单塞入delete。删除不查引用、不级联，语义交编译，完整性保护仍保留。不要把变量声明塞进正文或编辑只读快照。
4. 逐条检查退出码及JSON状态后再继续。备份成功、当前原文/哈希和完整回读不能省。保存后重新导出用于后续修改；同一工程/会话串行执行。
5. 分别报告缓冲更新、原生保存、回读、用户编译反馈和业务行为验证。只读或本地候选任务完成后，不额外写入/保存。

离线开发先export冻结直接HCP和依赖，再check/build，使用返回的plan摘要apply；所有备份先于首写，完整回读后由用户重开并编译。不要自动关闭用户工程。HCP占用时，已有正文可沿原registration-capture及editor-read/sync的--registration-receipt路径；声明/创建等改读[独立项目登记基线](references/project-registration.md)，按已支持CLI显式绑定。两种凭据不混用、不默认信任旧HCPP，保存后旧文件基线失效，捕获命令本身不关开工程。

常用只读调用：

```powershell
python -B $bridge code-context --project $project --symbol CalcDemo --max-items 20
python -B $bridge scan $project --output "$artifacts/scan.json"
python -B $bridge export "$project/CalcDemo.FC" --workspace "$artifacts/calc-work"
python -B $bridge source-read "$artifacts/calc-work" --start 1 --limit 20
```

以上`CalcDemo`及路径组成仅为合成示例；真实文件路径/名称从当次扫描取得，原生文件可能位于工程子目录，不能假定都直接放在工程根目录。先用limit安全读取；只有已知实际行数时才用end。`exported`只表示导出；`source_patch_ready`/`source_patched`分别是本地补丁预检/修改；`ready`/`editor_ready`是对应写入预检；`built`是候选；`replaced`是原生写入或恢复；`editor_updated_not_saved`是缓冲修改；`editor_saved`及`editor_saved_closed`是保存。编译文本`reported_pass`不是工具证实本轮编译。完整能力及验证范围见[能力边界](references/capabilities.md)。

## 必须停止的情况

- 退出非0、`blocked`、目标/PID歧义、未知格式/布局、未保存用户内容、磁盘与缓冲基线不同、备份失败、模态提示或结果不确定：停止依赖写入。先保存诊断摘要/备份路径、只读核对当前状态，再决定恢复或请求用户处理；不盲目重放写入、不保存旧窗口、不假定回滚。
- 旧文件入口发现行数变化或FB/FC行记录滞后，不能手补元数据；关闭工程后的ST/FB按离线参考检查已实现profile。s22的offline FC仅接受正文/行表匹配且三个未知行字段全零的输入，写正文时保留完整旧行表，输出可能滞后，不能制造新LF行表或直接续写旧工作目录。未知值按具体行/字段/值报告，不清零绕过；详见[FC说明](references/data-editing.md)。嵌套/值初始化等范围另列，单程序上限1000行（LF数+1，含空行）。
- 默认scan仍仅识别`LD`；独立梯形图入口支持已观察格式的只读记录查询，未知布局拒绝。含内嵌ST禁止整图复制，先读磁盘正文，当前物化控件另读且不冒充完整实时混合图。系统变量只读；不编辑梯形图、不自动编译、不从编译面板取结果，不做PLC下载、启停或强制IO。更多未开放范围见能力表。

## 结果交付

说明目标与修改/只读范围、产物和不可覆盖备份位置、实际JSON状态、完整回读与非目标检查结果；明确哪些仅离线/模拟、哪些是用户本轮编译反馈、哪些未验证。错误只给必要对象/阶段和诊断，不输出整个工程或敏感内容。

需要部署验收或重放冒烟时，再读[两项目验收](references/validation.md)；普通读取/编辑任务无需加载验收文档。试用结果保存在包外开发记录，不作为新AI的操作答案。不能把合成容器当成AutoShop已编译工程。
