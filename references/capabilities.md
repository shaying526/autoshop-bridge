# 能力和证据边界

s20已实现方法二点限定库类型及已登记LD功能块引用：LiteST宿主VAR使用editor-variables，全局FBI使用instances-editor-add的FB专用真实选择器。准确根定义和可读文件哈希取代递归业务依赖证明；未登记点限定VAR先为`ide_resolved`，保存后依据原生64/256确认实际类型。空表及只有复杂声明的FB表支持备份后默认行和延后选择器预检。方法二未登记单段库名、直接修改LD宿主仍待。正常保存、重开完整回读、组合及恢复0错误编译已限定验收；1623项回归通过（1项主机权限跳过），不以历史结果代替本次调用验收。示例及执行细节见[变量与表](data-editing.md)。

s21方法一库/已登记LD实例为开发待验：LiteST宿主VAR库add可用`type_kind:"function_block"`显式选原生256种类，FBI天然FB、不加此字段。直接HCP识别准确登记LD原名称，不解析图形；VAR原生类型文本大写，FBI原样，null请求/空默认初始化。库存在性及语义交编译，外部安装库不宣称被冻结。正常样本10记录exact/3整文件exact、正式单项/批量check/build/apply及非目标保持已过；重开独立分类3个新FBI flags 0→256、其他49源exact，完整读表和两次0错误编译均通过。本包为s21；历史验收不替代调用者本次工程验收。

平面BOOL/INT/DINT结构的混合空/非空成员注释两模式及正规rename已实现同一默认模板，按原成员末项位置保留分隔符，末尾`, `不得trim；全空、全非空及`=`/`#`保持原行为。GVT仍用独立空初始化串。嵌套/值初始化等语法仍另待，不清空注释绕过。

FBI新增采用新行完整11列、全部名称/计数/唯一ID逐步校验，保存前后完整读表。`allocation_preview`区分显示预览和原生值；只有IDE保存的旧地址4字节准确等于写前完整UI快照、且该旧记录除这4字节外全部保持时，新增入口才接受并列`native_allocation_updates`，scope为`editor_preview_with_native_updates`；未发生此类保存差量时为`not_saved_native_allocation`。其他字段与其他默认入口仍严格检查，不能概称IDE保存永不修改旧原记录，也不能把UI预览当已保存地址。

已有FBI实例支持名称/注释/初值编辑：[用法](data-editing.md#fbi已有实例编辑)。offline修改完整原生字符串，编辑器使用正常工具箱成员初值；类型/顺序/地址及其他元数据保持，不新增业务语义证明。已有字段不要求全工程类型完整解析。文件改名不更新引用；IDE改名可能自动保存引用，事先保护全部原生源码并返回实际清单，不要求引用完整。未物化的任意嵌套界面展开、未知关联布局及超出已知字符串编码范围另待，不等同禁止普通编辑。

s18补齐全局FBI的文件模式项目FB实例追加：严格已识别双表容器、已有LiteST项目类型、null默认值、非空批量和空表首二项；完整基线/唯一备份/回读保持，正文引用由AI组织，不构造未知容器或内存地址。命令及边界见[离线编辑](offline-editing.md#全局fbi项目fb实例s18)，实际证据见[验收](validation.md)。

s17支持已登记LiteST FB内部VAR项目FB实例的文件新增，含空表首项与批量追加：initial_value:null，正常IDE已观察的大写类型文本/空默认记录，不复制初始化或地址。带结构接口、内部项目FB、已有库成员的引用定义已在独立副本加载/回读及组合编译0错误；调用正文由AI显式修改。方法二兼容实际大写显示，详见[离线用法](offline-editing.md)、[验收](validation.md)。

s16补齐严格空GVT：BOOL/INT/DINT首项及追加两模式可用；已有扁平结构首项/第二项文件模式用offline，编辑器用table-editor-edit。空表结构dry-run报告延后选择器预检且不创建行，真实执行先备份和默认行核对；仅结构表后续追加不再强制已有标量。未知空布局及新空白工程HCPP资格另待，见[变量与表](data-editing.md)、[验收](validation.md)。

s15支持offline系列的已识别ST非零词法折叠缓存及增删行，原全零profile保持；相同逻辑行保留字段，新行中性初始化，未知值返回具体行/字段/值。独立37→28候选、增删行与完整回读/编译证据见[验收](validation.md)及[离线用法](offline-editing.md)。不增加自动业务引用同步。

s14补齐严格空FBI编辑器首项/第二项、dry-run延后预检和两模式删空；正式保存/重开/完整回读及恢复编译证据见[验收说明](validation.md)。不因旧引用阻止删除，不生成未知原生容器。

新增[结构成员正规改名](structure-renaming.md)：单项/批量名称及已解析ST FB关联初值成员键；不自动替换正文引用，允许调用者另改正文后编译。其余尚未实现字段与格式边界分别列明，不以旧白名单禁止正常工程编辑。

s11新增FC标量声明：方法二空表首项/第二项正常保存、重开回读与编译0错误已验；方法一独立FC编码的12种BOOL/INT/DINT×VAR/IN/OUT/INOUT组合从空表写入、加载/完整回读和编译0错误已验。初值仅null，旧记录/完整正文行表保持，闭工程独占/基线/备份/恢复保护保留。首次注释单元格曾超时并留下已知未保存行，经核对后受控继续；另从全新空表正式命令连续成功。不得把一次成功当桌面时序保证。FC复杂类型、返回类型、FCI和离线正文增删行仍未实现。

s10仅修复既有正文凭据路径：关闭捕获的直接HCP、当前进程/对象树、全部冻结文件及干净目标正文联合校验；HCP不可读时旧镜像差异仅作提示，不替换依赖集合。返回current_hcp_verified=false及有界registration_hint差异，不能显示为实时HCP已读取。独立副本真实捕获→同进程打开→读取→注释保存→完整回读通过；保存后旧凭据仍拒绝。其他类型目录/创建/离线资格不变，详见[凭据说明](offline-editing.md)。

s10 / CLI 1.03保留[关闭工程离线开发](offline-editing.md)：offline-export/check/build/apply/restore仅编辑已登记对象，独占HCP、全部备份、候选重建及完整回读。更新FB内部VAR结构和方法二GVT结构新增；加入[明确声明删除](declaration-editing.md)，两模式支持ST/LiteST FB、FC、结构、GVT及FBI。FB/FC/GVT/FBI可在已观察严格profile删空，STRU保留至少一成员；空FBI编辑器首项/第二项已实现。删除不查引用、不级联，语义交编译；完整性保护保留。registration-receipt仍只验证目标正文，不能用来授权类型或创建。嵌套/数组及FC离线增删正文行仍另待；混合结构成员注释在s20扩展，空GVT首项已在s16补齐。新CLI不增加service.__all__入口。

整理方式：AI 根据后台1.03代码、公共接口及既有验收报告整理  
当前状态：s21方法一库/LD限定真实验收通过；完整包提供  
最后更新：2026-10-29

所有公共能力仍由原CLI或`autoshop_bridge.service.__all__`提供，没有新增MCP/业务API。CLI的`命令 --help`是参数事实来源；下表是可用范围，不表示每种类型组合都在AutoShop实测。

s9已观察V4.11.0.5正常界面保存：扁平结构成员注释中的ASCII `=`和`#`原样进入FB结构初始化串，独立副本INOUT端口及GVT结构变量分别完整回读、编译0错误。`(),:`等未验语法及其他未知ST行字段限制保留；s15已单独补齐可识别非零折叠缓存；详见[离线编辑](offline-editing.md)。HCP占用、严格类型目录和可能过时镜像未因此解决。

s6另有[梯形图独立只读脚本](ladder-reading.md)，不属于上述公共service或默认scan；其输出保留experimental标记，不把接口已提供等同完整逻辑语义已验证。

| 任务 / 入口 | 输入与输出 | 副作用 / 依赖 | 实现及验证 |
| --- | --- | --- | --- |
| 梯形图文件读取：inspect_autoshop_ladder.py | 已知LD/LD型FB绝对路径；摘要、FB变量、按网络分页图元/引脚/连接及内嵌ST | 不依赖HCP或AutoShop；只读已保存文件，不读取未保存缓冲 | 已观察格式实验支持；Windows10/V4.11.0.5样本界面核对，未知布局拒绝；不是完整语义解释器 |
| 梯形图窗口读取：inspect_autoshop_ladder_editor.py | 工程/对象/PID；普通图完整复制后分页、变量或物化ST控件 | Windows/已打开标签；可显式激活，复制有选择/剪贴板副作用；不改逻辑/保存 | 普通LD/FB已验，含ST整图复制禁止，物化控件不证明完整实时混合图；具体恢复边界见读取说明 |
| 工程摘要/扫描：project-summary、scan | 绝对工程目录或唯一HCP；有界摘要或完整JSON文件 | 读取磁盘/登记镜像，可能标记possibly_stale；不反映未保存缓冲 | 已实现，既有工程只读验收；完整编译器语义未实现 |
| 检索：code-context、code-query | 符号、关系、limit/offset；定义/引用/调用/直接影响候选 | 磁盘只读；coverage=partial，词法候选非确定调用图 | 已实现，样本与自动检查；传递影响/完整作用域未实现 |
| 正文：export、source-read/patch/restore | 原生ST/FB/FC→工作目录source.st；唯一原文补丁/哈希→差异、片段、备份 | 导出/补丁写外部工件；variables.json只读 | 已实现；限定正文及增删行有原后台用户编译证据 |
| 文件直改模式：check/build/apply、backup/restore | 工作目录/原生基线；候选、替换结果、唯一备份 | apply/restore写原生；覆盖前校验和备份；非工程事务 | 已实现；ST/FB/FC正文同LF及限定表操作有历史验收，未知元数据不生成 |
| 正文编辑器：editor-open/read/sync/save/close | 工程、准确程序名、可选PID、工作目录/快照；缓冲/保存/回读状态 | Windows/已打开工程；可自动打开标签，sync默认不保存 | 已实现；ST/FB/FC正文限定场景保存及人工编译已验，其他版本/桌面未验 |
| FB/FC变量：editor-variables | schema=1操作清单、原生哈希；整表和保存结果 | 改缓冲，显式保存；复杂类型/依赖和整表保护 | 已实现限定范围，见[变量操作](data-editing.md)；并非所有组合现场验收 |
| 结构/GVT：table-export/check/build/apply、table-editor-read/edit/close | 独立table工作目录/changes.json；成员/声明、候选、备份、保存结果 | 文件及编辑器两模式；GVT新增核对全部同目录GVT | 限定字段及BOOL/INT/DINT普通新增两模式历史编译通过；DINT既有初值修改/极值只有自动测试 |
| 全局FB实例：instances-editor-read/add、offline系列 | 准确表名、清单、FBI哈希；完整表、备份、分配预览与实际地址更新清单 | 方法二非空/严格空表使用FB专用选择器；方法一s21扩展已登记LD/点限定库FB，天然256且无type_kind；保存不等于编译 | s20方法二库/LD已有联合验收；s21方法一正常样本及单项/批量磁盘流程通过，完整读表和组合/恢复0错误编译通过，本包提供；任意容器构造未实现 |
| 明确删除：declarations-read、editor-declarations-delete、offline系列 | 准确对象/模式、文件及记录哈希、delete清单；候选/缓冲/保存/回读分阶段状态 | 不检查引用、不级联；完整身份/备份/基线/非目标保护，未知布局拒绝 | 两模式、FB/FC/GVT/FBI严格profile删空已在V4.11.0.5独立副本验证；STRU末项菜单禁用 |
| 系统定义：system-variables-read | 工程+用户本机安装definitions-dir；表/类型/search有界结果及来源哈希 | 只读厂商XML，随包不带XML，不是PLC实时值 | 已实现；单型号、部分表与窗口核对，其余型号/地址单位未验；SVT不是空GVT |
| 编译反馈：build-baseline/report | 本轮基线与用户取得的真实日志；reported_pass/fail/未解析诊断 | 仅写报告；compile_freshness=unverified | 已实现文本解析，真实故意错误/修复有历史人工反馈；自动编译、面板读取未实现 |
| 多对象：change-check/run | source/table步骤及依赖计划；逐步日志、失败及未执行清单 | 同一组同一种模式；editor步骤保存；无原子性/自动回滚 | 已实现；两步历史保存/编译通过，中断恢复仅自动检查；变量新增不在组内 |
| 新建：object-dialog/create-st；实验object-plan/create | ST从已观察对话框起步；实验计划指定litest-fb/structure、名称、初始正文/成员及完整基线 | AutoShop生成容器/登记，显式save-project才保存工程登记；不覆盖同名，失败可能已创建，不盲重试 | LiteST FB及标量结构已在独立测试场景保存、重开、用户编译验收；不属稳定service；未知HCPP仍可能阻止创建，正文凭据不授权创建；新FC、新空白工程未知HCPP严格登记未完成 |

原后台现场基准：Windows10、AutoShop V4.11.0.5、Python3.9.1；308项回归是V1.02历史自动结果。Python3.12仅更早阶段离线检查，不是当前新增能力或真实IDE已验。分发包的实际本轮结果见[验收说明](validation.md)，不能继承为本包已做真实编译。

默认scan/公共service对梯形图仍只返回`language=LD`/`ladder_not_supported`；独立读取入口不改此语义，不提供梯形图写入/排序。硬件、轴/总线配置、PLC下载/启停/强制IO、MCP、安装器、异步进度/取消、稳定业务错误码及自动编译均不在本次交付。
