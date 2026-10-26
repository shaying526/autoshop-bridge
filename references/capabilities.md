# 能力和证据边界

新增[结构成员正规改名](structure-renaming.md)：单项/批量名称及已解析ST FB关联初值成员键；不自动替换正文引用，允许调用者另改正文后编译。其余尚未实现字段与格式边界分别列明，不以旧白名单禁止正常工程编辑。

s11新增FC标量声明：方法二空表首项/第二项正常保存、重开回读与编译0错误已验；方法一独立FC编码的12种BOOL/INT/DINT×VAR/IN/OUT/INOUT组合从空表写入、加载/完整回读和编译0错误已验。初值仅null，旧记录/完整正文行表保持，闭工程独占/基线/备份/恢复保护保留。首次注释单元格曾超时并留下已知未保存行，经核对后受控继续；另从全新空表正式命令连续成功。不得把一次成功当桌面时序保证。FC复杂类型、返回类型、FCI和离线正文增删行仍未实现。

s10仅修复既有正文凭据路径：关闭捕获的直接HCP、当前进程/对象树、全部冻结文件及干净目标正文联合校验；HCP不可读时旧镜像差异仅作提示，不替换依赖集合。返回current_hcp_verified=false及有界registration_hint差异，不能显示为实时HCP已读取。独立副本真实捕获→同进程打开→读取→注释保存→完整回读通过；保存后旧凭据仍拒绝。其他类型目录/创建/离线资格不变，详见[凭据说明](offline-editing.md)。

s10 / CLI 1.03保留[关闭工程离线开发](offline-editing.md)：offline-export/check/build/apply/restore仅编辑已登记对象，独占HCP、全部备份、候选重建及完整回读。更新FB内部VAR结构和方法二GVT结构新增；加入[明确声明删除](declaration-editing.md)，两模式支持ST/LiteST FB、FC、结构、GVT及非空FBI。FB/FC/GVT可删空，STRU保留至少一成员，空FBI增删仍未实现。删除不查引用、不级联，语义交编译；完整性保护保留。registration-receipt仍只验证目标正文，不能用来授权类型或创建。混合结构成员注释、嵌套/数组、空GVT首项、FC离线增删正文行的限制保持。新CLI不增加service.__all__入口。

整理方式：AI 根据后台1.03代码、公共接口及既有验收报告整理  
当前状态：s9修复结构初值注释误拒绝；后台现场证据与本包合成验证分开  
最后更新：2026-10-26

所有公共能力仍由原CLI或`autoshop_bridge.service.__all__`提供，没有新增MCP/业务API。CLI的`命令 --help`是参数事实来源；下表是可用范围，不表示每种类型组合都在AutoShop实测。

s9已观察V4.11.0.5正常界面保存：扁平结构成员注释中的ASCII `=`和`#`原样进入FB结构初始化串，独立副本INOUT端口及GVT结构变量分别完整回读、编译0错误。`(),:`等未验语法及MAIN类ST的非零未知行字段限制保留；详见[离线编辑](offline-editing.md)。HCP占用、严格类型目录和可能过时镜像未因此解决。

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
| 全局FB实例：instances-editor-read/add | 准确表名、清单、FBI哈希；整表、备份和软件分配地址 | 新增只支持非空已识别实例表中的已解析项目FB；保存不等于编译分配完成 | 已实现；明确非空删除另走下行，已识别FBI原件可backup/restore；库实例、空表新增及任意容器构造未实现 |
| 明确删除：declarations-read、editor-declarations-delete、offline系列 | 准确对象/模式、文件及记录哈希、delete清单；候选/缓冲/保存/回读分阶段状态 | 不检查引用、不级联；完整身份/备份/基线/非目标保护，未知布局拒绝 | 两模式、FB/FC/GVT删空及FBI非空已在V4.11.0.5独立副本验证；STRU末项菜单禁用；FBI删空未实现 |
| 系统定义：system-variables-read | 工程+用户本机安装definitions-dir；表/类型/search有界结果及来源哈希 | 只读厂商XML，随包不带XML，不是PLC实时值 | 已实现；单型号、部分表与窗口核对，其余型号/地址单位未验；SVT不是空GVT |
| 编译反馈：build-baseline/report | 本轮基线与用户取得的真实日志；reported_pass/fail/未解析诊断 | 仅写报告；compile_freshness=unverified | 已实现文本解析，真实故意错误/修复有历史人工反馈；自动编译、面板读取未实现 |
| 多对象：change-check/run | source/table步骤及依赖计划；逐步日志、失败及未执行清单 | 同一组同一种模式；editor步骤保存；无原子性/自动回滚 | 已实现；两步历史保存/编译通过，中断恢复仅自动检查；变量新增不在组内 |
| 新建：object-dialog/create-st；实验object-plan/create | ST从已观察对话框起步；实验计划指定litest-fb/structure、名称、初始正文/成员及完整基线 | AutoShop生成容器/登记，显式save-project才保存工程登记；不覆盖同名，失败可能已创建，不盲重试 | LiteST FB及标量结构已在独立测试场景保存、重开、用户编译验收；不属稳定service；未知HCPP仍可能阻止创建，正文凭据不授权创建；新FC、空FBI首项未完成 |

原后台现场基准：Windows10、AutoShop V4.11.0.5、Python3.9.1；308项回归是V1.02历史自动结果。Python3.12仅更早阶段离线检查，不是当前新增能力或真实IDE已验。分发包的实际本轮结果见[验收说明](validation.md)，不能继承为本包已做真实编译。

默认scan/公共service对梯形图仍只返回`language=LD`/`ladder_not_supported`；独立读取入口不改此语义，不提供梯形图写入/排序。硬件、轴/总线配置、PLC下载/启停/强制IO、MCP、安装器、异步进度/取消、稳定业务错误码及自动编译均不在本次交付。
