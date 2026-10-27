# 关闭工程后的离线编辑

s17补齐已登记LiteST FB内部VAR的项目FB实例新增，含空表首项和批量追加。使用下文原offline系列及完整保护，详见[内部实例专项](validation.md)。

s16新增严格空GVT首项/第二项：标量和已支持扁平结构复用本页variable_operations/add格式及全量保护，不新增profile开关。正常IDE保存与候选整文件匹配，实际重开回读通过，原12项加本轮5项编译0错误；见[专项报告](validation.md)。未知空布局、新空白工程未知HCPP资格另待。

整理方式：AI 根据实现与独立副本验证整理  
当前状态：CLI 1.03实验扩展；独立副本加载、正文/表回读和编译通过，发布包另做完整性验证  
最后更新：2026-10-26

处理已创建并登记的ST、LiteST FB、结构、全局变量表和FBI实例表，不新建对象、不改HCP。保存所需修改并关闭整个目标工程，关闭FB标签不足以重载；无需退出AutoShop。输出和备份必须在工程及Skill安装目录外。当前为同步CLI和内部Python工作流，不属于service.__all__的稳定接口。

## 命令与路径

开发工作树新增FC标量声明编码（[本轮报告](validation.md)，12个类型/类别组合已加载/回读及编译0错误，已纳入s11）：目标必须是已登记并严格可解析的ST型FC，variable_operations仅add，支持BOOL/INT/DINT及VAR/IN/OUT/INOUT，initial_value必须null。示例：`{"file":"CalcDemo.FC","variable_operations":[{"op":"add","name":"inputValue","category":"IN","data_type":"INT","initial_value":null,"comment":"Input"}]}`。FC新增不能带source_file，不能与delete混用；不支持set、复杂类型或返回类型。独立三尾字段记录不含FB初值/保持字段，原记录及整个内层正文/行表保持原字节；已有正文行表滞后不靠新增变量改写。闭工程、直接HCP、全部基线/唯一备份和完整回读保护与其他offline目标相同。

以下变量均由本次任务提供，使用绝对路径。bridge指向autoshop_bridge_cli.py。可从其他工作目录调用。

```powershell
python -B $bridge offline-export --project $project --workspace "$artifacts/offline-work"
python -B $bridge offline-check --workspace "$artifacts/offline-work" --changes "$artifacts/changes.json"
python -B $bridge offline-build --workspace "$artifacts/offline-work" --changes "$artifacts/changes.json"
# 使用built返回的实际plan和plan_sha256，不自行改plan或candidate。
python -B $bridge offline-apply --plan-file $plan --expect-plan-sha256 $planHash --backup-root "$artifacts/backups" --experimental
# 仅在需要恢复且当前文件仍匹配apply后哈希时调用，恢复前再次备份。
python -B $bridge offline-restore --receipt-file $receipt --expect-receipt-sha256 $receiptHash --backup-root "$artifacts/recovery-backups" --experimental
```

exported冻结直接HCP、所有现存登记文件和额外原生文件。没有独立文件的登记列入excluded_nonfile_registration；原本缺失的非原生配置列入declared_missing，必须保持不存在。两者不成为可写目标；缺失原生依赖拒绝。HCPP不签发离线写资格。export/check/build只读，不证明工程已关闭；apply/restore全程保持Windows独占只读HCP句柄。用户仍须关闭工程，独占句柄不能证明其他软件没有旧内存内容。

checked已做正文、格式、类型和命名预检；built仅生成候选。apply核对外部plan摘要、全部基线，再从冻结请求完整重建候选并逐字节比较。所有唯一备份必须先于首写完成且回读通过；写后完整回读并检查非目标文件。applied只证明磁盘阶段，重新加载、软件保存和编译分别验收。

## 全局FBI项目FB实例（s18）

### 已有实例的名称、注释和初值

已有实例使用`set`，字段为`name`、`comment`、`initial_value`。`expected`和`value`均为明确字符串；初值用完整原生初始化串，清空用`""`，不是新增的null。旧值从本轮`declarations-read`或原生实例读取获得；声明表隐藏初值预览不等于该原生串。操作按顺序执行，改名后的后续操作使用新名称。

```json
{
  "schema": 1,
  "targets": [{
    "file": "Instances.fbi",
    "variable_operations": [
      {"op":"set","name":"fbTimer","field":"name","expected":"fbTimer","value":"fbTimerNew"},
      {"op":"set","name":"fbTimerNew","field":"comment","expected":"Old comment","value":"New comment"},
      {"op":"set","name":"fbTimerNew","field":"initial_value","expected":"","value":"(IN:=OFF, PT:=250, Q:=OFF, ET:=0, iRecordCount:=0)"}
    ]
  }]
}
```

沿本页export/check/build/apply/restore执行；名称/注释/初值仅替换指定字符串，顺序、类型、地址及其他元数据、其他记录和前后容器保持。初始化正文由调用者按实际类型组织，工具不增加成员/表达式语义证明。已有字段无需递归解析类型定义，不因无关FB/LD/结构未解析而阻断。仅原生表示、身份和已知重名资格检查，保留完整基线/备份/回读；未知容器仍返回格式未实现。

文件模式改名**不更新正文引用**。调用者可在同批请求中显式添加ST的source_file，也可另行修改正文；保留旧引用允许执行，最终由AutoShop编译检查。不自动级联或回滚业务改动。

编辑器方式另有`instances-editor-edit`。名称和注释使用上述单条set对象；初值通过真实工具箱成员编辑，使用`{"op":"set","name":"fbTimer","field":"initial_value","member":"PT","expected":"0","value":"250"}`。先用`instances-editor-initial-read --project $project --table $table --instance fbTimer --pid $pidValue --output "$artifacts/initial.json"`读取实际成员值及独立原生全文；不要从声明表隐藏栏猜旧值。编辑器请求外层是`{"schema":1,"operations":[...]}`，命令参数与instances-editor-add一致，需本次原生SHA256及experimental，显式save才保存。

正常IDE改名可能在目标表保存前自动修改并保存正文引用。该路径先保护全部原生源码及登记证据，返回reference_updates清单、每文件前后哈希和实际名称替换数；不要求全部引用已更新。未改动的未知对象不解析，实际关联文件发生未支持格式变化时保留备份并明确停止，不猜写未知字节。工具箱初值按准确实例/已显示成员路径修改，完整回读整表及该实例成员；IDE可能排序、规范成员名大小写，保存后返回native_initializers原生全文，其他记录及元数据保持。

本轮已完成独立副本两模式及恢复的完整回读、三次0错误编译；随s19交付。真实结果与仍未实现范围见[FBI字段专项](validation.md)。同批可先add默认实例，再用set提供完整原生初值；新增构造范围仍以已有add支持类型/profile为准。

目标为准确登记的FBI文件，命令沿用上文offline-export/check/build/apply/restore，工程须关闭。add没有category，不把全局实例当普通GVT或FB内部VAR记录。示例中的文件及类型名须换成当次登记对象：

```json
{"schema":1,"targets":[{"file":"Instances.fbi","variable_operations":[
  {"op":"add","name":"timerA","data_type":"TimerBlock","initial_value":null,"comment":"First global timer"},
  {"op":"add","name":"timerB","data_type":"TimerBlock","initial_value":null,"comment":"Second global timer"}
]}]}
```

空表首项、第二项及非空批量同格式，每目标1–32项，最多4096声明。引用类型须是精确登记并可解析的LiteST项目FB；FBI原生类型文本保留准确名称大小写，不套用内部VAR的大写规则。新记录为空初始化、flags0和FFFFFFFF未分配地址，AutoShop加载/编译负责布局和分配，不生成传递初始化，不改类型定义或旧实例。V4.11.0.5正常加载可把新记录flags从0改为256，编译再分配地址；完整语义未解码，工具不预写256绕过。加载/编译后需重新获取基线，不重放旧plan。库名、LD FB、显式复杂初值及其他字段尚未实现。

新增只接受已观察双表容器：移除声明后须严格匹配完整已验空表与共享CArchive状态。唯一记录段能读、能删除，不表示任意容器可新增。未知布局返回offline_unsupported_fbi_layout，context包含profile、field，能定位记录段时提供record_segment_offset和record_segment_bytes，否则给出original_error；显式初值返回offline_unsupported_fbi_initializer，未知类型返回offline_unsupported_fb_instance。目标格式拒绝补target及相关操作/变量/类型，不要求调用者修改未知字节或清零绕过。

工具检查已解析GVT/FBI、工程对象及同批新增名称；仅新增FBI时，无法解析的同级对象仍全部冻结/备份，不作为目标新增的语义门槛；混合GVT请求沿用既有GVT资格，不宣称已证明所有业务引用/类型使用正确。正文由调用AI另作source_file目标组织，不向FBI添加source_file，也不自动绑定调用。重开工程后用instances-editor-read完整核对，再另行编译；applied只证明磁盘写入与回读。身份、未保存状态、全部基线/唯一备份、候选重建及非目标保护保持。

## FB内部项目FB实例（s17）

使用现有 `variable_operations`，目标为已登记LiteST FB，引用类型名取直接HCP登记与原生FB头的准确名称。工程关闭后按上文export → check → build → apply；不需要新命令或profile参数。

```json
{"schema":1,"targets":[{"file":"Controller.FB","variable_operations":[
  {"op":"add","name":"timerA","data_type":"TimerBlock","category":"VAR","initial_value":null,"comment":"First timer"},
  {"op":"add","name":"timerB","data_type":"TimerBlock","category":"VAR","initial_value":null,"comment":"Second timer"}
]}]}
```

`Controller`和`TimerBlock`仅为合成名称，必须换成实际登记对象。空表和非空表采用相同清单；每个目标最多32项。新记录采用正常IDE保存已观察的类型码256、FB类型名大写形式（如TimerBlock→TIMERBLOCK）、空初始化串及VAR/不保持/未分配字段；初值必须null，显式复杂初值、FB类型的IN/OUT/INOUT、库名或LD FB的离线新增尚未实现。传入正确登记名，读回大写类型文本属于IDE原生规则，不手改类型文件或只读快照“修复”大小写。

内部实例不使用全局FBI容器，不生成地址、传递布局或结构成员初始化串；已有记录的初始化、类型拼写、全部字段和顺序原样保留。仅验证本次所需FB定义的登记、可解析容器及准确头部，所有文件哈希仍被冻结。不因无关LD/FB未解析、引用FB中已有库/结构成员或正文尚未修完而拒绝这个已支持的记录新增；不推导编译语义或自动更新调用。正文引用由调用者另改；可在同一目标显式加入source_file，多文件安排同样由调用者组织，最终交AutoShop编译。

重开工程后用editor-read完整核对正文、声明及未保存状态，编译另行执行。方法二同样接受已观察的FB类型大写显示，仍逐格核对整表和备份。编译通过不表示PLC行为已验证。

## 结构注释预检修复（2026-10-26 / s9）

旧s8把ASCII `=`误列为未观察分隔符。独立副本中正常界面保存的17/31成员结构INOUT初始化串，与保留原注释的候选逐字节一致；GVT结构声明使用独立空初始化串，不套用FB语法。两种路径实际加载、完整窗口回读及全部编译0错误已分别验证。

未观察的分隔符返回 `offline_initializer_comment_unobserved`，含 `error_context`：target、operation_index、variable、category、structure、member、member_index、field、原comment、characters及character_positions、index_base=0、reason与requires。操作、成员和字符索引为0基；错误正文的成员序号为1基。普通候选格式拒绝保留 `offline_invalid_request`，补target和original_error；冲突继续 `offline_conflict`。调用方须处理未知错误码，不靠匹配错误文案判断状态。诊断可能含原注释，分享日志前审阅。

这不增加格式通用性：混合空注释、嵌套、数组等原限制保留。ST若有非零未知行字段仍拒绝，不能清零或压成一行绕过；结构初值修复不保证完整多目标请求通过。check/build不写工程；apply/restore的独占句柄、全部基线、唯一备份、完整候选重建及回读保护未变。

## changes.json

```json
{
  "schema": 1,
  "targets": [
    {
      "file": "Block.FB",
      "source_file": "body.st",
      "variable_operations": [
        {"op":"add","name":"bEnabled","data_type":"BOOL","category":"VAR","initial_value":"OFF","comment":"Local flag"},
        {"op":"add","name":"stInput","data_type":"InputData","category":"INOUT","initial_value":null,"comment":"Input structure"}
      ]
    },
    {
      "file": "Globals.gvt",
      "variable_operations": [
        {"op":"add","name":"gInput","data_type":"InputData","initial_value":null,"comment":"Input data"}
      ]
    }
  ]
}
```

file为登记中准确的相对路径。source_file相对changes.json目录解析，为UTF-8无BOM正文，不相对当前工作目录。禁止绝对成员路径、目录逃逸和链接。不修改变量时省略variable_operations；不修改正文时省略source_file。支持1–100目标；FB/GVT每目标1–32变量操作。正文上限1000行（LF+1，含末尾空行）。同一FB先构建变量候选，再处理正文。

FB add字段如上。VAR/IN/OUT的BOOL/INT/DINT初值为OFF/ON或规范十进制字符串，INOUT必须null。结构VAR/IN/OUT/INOUT要求已登记、非空、扁平BOOL/INT/DINT定义及null初值；成员注释目前仅全空或全部非空可用。V4.11.0.5 实际INOUT保存确认ASCII `=`、`#`原样编码、不转义，原注释逐字保留；ASCII `(`、`)`、`,`、`:`仍未验证，继续拒绝。混合注释、嵌套、数组、STRING拒绝。set仅既有注释或标量初值，精确字段为op/name/field/expected/value；默认已验范围不包含类别/类型修改。结构VAR新增编码与真实IDE已保存记录逐字节匹配，文件模式覆盖/重开尚未单独验收。

开发CLI已接入FB/FC/GVT可删至空、结构保留至少一成员的明确删除：variable_operations使用op/name/expected_record_sha256三字段的delete项，不与add/set混用。按用户原则不查引用/调用/类型使用者，不因其他LD/FBI及内嵌登记未解析而阻断，不级联；对象身份、全部基线/备份、候选重建及完整回读保护保留。FB可显式附source_file修正文，FC删除不支持source_file，FC增删行仍未实现。FBI非空结果删除已接入CLI并实际保存验证，方法一apply/重开回读70项及恢复71项已验证，00:40:05恢复编译0错误；FBI严格profile删空已补齐，空表首项/第二项由instances-editor-add实现；限定FBI离线新增见s18段落，任意容器构造仍未实现；FB/FC/GVT删空两种模式已保存/回读验收，STRU末项菜单灰色，删除扩展分发状态以包清单为准。四目标磁盘apply/restore/reapply及重开完整回读已通过，故意保留正文引用时编译报预期未定义变量；四目标恢复后00:09:32全部编译0错误，后续00:25:28恢复编译0错误及最终窗口回读已通过，见[删除专页](declaration-editing.md)。

GVT add精确字段为op/name/data_type/initial_value/comment。结构必须initial_value:null，新记录使用真实保存profile的未分配地址FFFFFFFF，交由IDE分配，不估算地址或复制旧地址。s16严格已识别空GVT也支持BOOL/INT/DINT和上述结构首项/后续追加，完整空容器前缀保持，未分配地址不复制。跨GVT/FBI及工程对象重名拒绝。同批修改结构再新增其引用暂不支持，分批刷新基线。结构表标量add/set复用原table逻辑，add没有category/initial_value。

ST增删行支持原全零profile及s15已识别的词法折叠缓存profile（depth/header/expanded）。按相同逻辑行迁移原记录，删除行移除记录，新增/替换行用正常IDE已观察的中性记录；重建UTF8字节长度、LF+1计数及顺序索引，前缀保持。AutoShop加载/保存自行刷新词法缓存，不证明业务语法。未知值返回offline_unsupported_st_row_metadata，error_context有target、line（1起）、row_index、field、value、byte_offset、profile和reason；不清零未知字段或压成单行。滞后ST行表仍拒绝。FB沿真实IDE保存行为保留完整旧行元数据，更新正文长度和字节、重定位变量造成的嵌入边界，不伪称滞后行表已刷新。FC增删行及LD写入不属于本入口；稳定旧build/apply限制保持。

s15实际37→28行的MAIN候选已在独立副本check/build/apply、恢复全115哈希、重放、重开完整回读及编译0错误；增行至30、删至27及回到原28行候选也已正式离线写入/重开回读。原结构/FB不重写，正文/引用及多文件安排由调用者负责。见[专项报告](validation.md)。请求仍为`{"schema":1,"targets":[{"file":"MAIN.ST","source_file":"MAIN-candidate.st"}]}`，source_file是相对changes.json的路径，不更换命令或额外传profile；用户需从实际工程重新export取得本轮基线。

## HCP占用时的目标正文凭据

FBI删除沿用原入口，新增按s18全局FBI段落执行；明确delete的零结果须完整匹配已观察empty_table profile，沿用全部基线/备份/摘要及候选重建检查；唯一实例记录段外opaque字节严格保持，不新增或重建未知容器。当前真实CLI编辑器删除保存已验证，文件方法重开70项及恢复71项回读已验证，00:40:05恢复编译0错误。[删除专页](declaration-editing.md)记录证据。通用backup/restore只扩展为严格可解析、profile与扩展匹配的FBI原件恢复，恢复前另做备份，不代表任意FBI生成能力。

HCP的共享限制仍存在。该路径先在工程关闭时取得直接HCP和依赖快照，再在同一AutoShop进程重开后，用实际工程树、原生哈希及当前正文/整表验证目标；HCPP仅提供有界登记提示，不被默认当作最新工程。适用于已登记ST/LiteST FB正文，不授权变量新增、类型目录、对象创建或整个工程配置修改。

```powershell
# 先由用户关闭目标工程；AutoShop仍运行，显式指定其PID，输出必须是新文件。
python -B $bridge registration-capture --project $project --program Block --pid $pidValue --output "$artifacts/target-registration.json"
# 用户重开同一进程的同一工程后执行；--open只打开指定程序标签。
python -B $bridge editor-read --project $project --program Block --open --registration-receipt "$artifacts/target-registration.json" --output "$artifacts/editor.json"
# export/patch后，用原editor-sync及其备份、保存回读规则；workspace是正文工作目录。
python -B $bridge editor-sync $workspace --project $project --program Block --open --save --experimental --registration-receipt "$artifacts/target-registration.json" --backup-root "$artifacts/editor-backups"
```

Python公共editor_read/editor_sync新增可选registration_receipt（Path，默认None）。不传保持原路径；registration-capture仅CLI/实验内部入口。凭据绑定工程、程序、PID/进程启动身份/主窗口、全部映射对象和全部登记文件状态及原生哈希，不是持久写授权。正文保存、依赖变化、对象树改变或换进程后失效，需重新关闭捕获；不能改凭据或HCPP绕过。首次导航和写前都再验证。当前只读树映射覆盖已观察程序/FB/结构/GVT/FBI类别，内部网络单独分类，FC及未映射配置树语义未开放；未知对象、配置文件变化或模态/未保存内容拒绝。

有界HCPP提取验证头部标识/版本、长度、CRC、解压流、全部成员/路径/重复和恰好四字节尾，不以1f000004的数值本身证明格式完整。未知头字段、尾值和语义仍保留证据；它们不签发写资格。只有闭时直接快照、当前树及内容证明共同满足才能进入上述正文路径。返回registration_evidence包含scope、hint_source和目标验证状态，不能对外描述为实时HCP读取已解决。

s10修复s9凭据路径把镜像哈希差异当作真实登记变化的误拒绝。HCP可读时仍严格核对直接HCP全部字节/登记行；HCP不可读时，镜像必须通过原有有界提取，但其差异只作为提示返回。目标映射、全部登记文件状态及额外原生依赖仍取自**未修改的关闭捕获凭据**，不能用旧镜像删减。当前进程/工程、完整映射对象树、原生文件哈希、干净编辑器全文/整表共同校验；导航前及实际写前再核对。保存后旧凭据仍失效。这个修复仅限显式正文凭据路径，不放宽变量/类型目录/对象创建或离线写入资格。

registration_evidence新增可选`current_hcp_verified:bool`及`registration_hint:null|object`。HCP被占用时前者为false；后者包括`authoritative=false,possibly_stale=true,matches_closed_snapshot,rows_match,captured_sha256,observed_sha256,captured_row_count,observed_row_count,archive_sha256,hcp_error,hcp_winerror,hcp_read_reason`及有界差异。不要把`rows_match=true`等同哈希一致或实时登记已证实。当前树只覆盖已映射对象，未映射配置的内存变化或HCP私有元数据不能全面证明；磁盘配置变化仍由冻结文件哈希拒绝。

凭据错误的CLI结果可含`error_context`：`evidence_source`区分direct_hcp、hcpp_hint_only、native_files、registered_files、live_process、live_session、live_project_tree、requested_binding等；`differences`逐项提供object/key/field/before/after及存在状态，最多32项，另有difference_count/truncated。镜像缺少旧快照对象的after=null仅表示镜像没有该对象，不表示当前工程删除了它。具体上下文可能有路径和注释，外发前审阅。源/树观察不稳定仍拒绝；纯读取可待稳定后重试，写入结果不确定时先检查现状。

registration错误码：registration_needs_refresh、registration_stale、registration_identity_mismatch、registration_scope_denied。所有新命令同步阻塞；没有取消/进度回调。方法二及凭据捕获需要Windows交互桌面和目标AutoShop；不会自动启动、关开工程或回应提示。Skill不交付自动编译/PLC命令。

## 失败与恢复

退出0且status=applied才表示磁盘阶段成功。退出1为error/stopped，退出2为partial。检查完整receipt、written/attempted和backup_run；失败可能已有部分写入，不盲目重试。恢复要求外部receipt摘要及当前apply后哈希，也先另做备份。多文件无事务，不承诺自动回滚或掉电原子性。整套本地元数据不是数字签名；调用方须保留build/apply返回的外部摘要。

offline错误码：offline_conflict、offline_project_unavailable、offline_invalid_request。操作系统文件错误统一为offline_project_unavailable，只有真实Win32共享32/33另带requires_close_entire_project；未知权限问题不猜原因。没有进度回调、取消或自动编译，超时后先检查状态。完整备份含非目标配置，文件多时有额外耗时。

实现：workflows/offline.py和formats/offline_source.py、offline_variables.py、offline_globals.py；Windows句柄守卫projects/offline_guard.py。[实际验证及限制](validation.md)。
