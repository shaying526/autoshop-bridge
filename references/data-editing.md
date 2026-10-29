# 变量、结构、全局表与实例

## FBI已有实例编辑

名称、注释、初值是已有实例的正常set操作，不需要删除重建或先证明引用、类型和业务正确。先读准确FBI文件及本次SHA256；未实现的布局与字段应明确说明，不能靠放宽检查或编辑只读快照绕过。

**文件模式**：工程关闭后使用[offline系列](offline-editing.md#已有实例的名称注释和初值)，目标variable_operations中采用`{"op":"set","name":"fbTimer","field":"name","expected":"fbTimer","value":"fbTimerNew"}`；comment和initial_value同样指定准确旧字符串/新字符串。初值是完整原生串，清空用`""`，不是新增时的null。用`declarations-read`读initial_value_raw，不能把声明表隐藏栏当原生全文。保留记录顺序、类型、地址和其他元数据、其他记录及容器。文件模式不更新正文引用；由AI另列source_file或随后修改正文，不因旧引用尚在而阻止改名，编译检查语义。

**编辑器模式**：先读取实际工具箱成员值，使用返回的native_sha256和明确旧值。读取会选中实例并改变焦点/滚动，不编辑或保存。

```powershell
python -B $bridge instances-editor-initial-read --project $project --table $table --instance fbTimer --pid $pidValue --output "$artifacts/initial-before.json"
python -B $bridge instances-editor-edit --project $project --table $table --changes "$artifacts/fbi-fields.json" --expect-sha256 $nativeHash --pid $pidValue --experimental --save --backup-root "$artifacts/backups"
```

```json
{"schema":1,"operations":[
  {"op":"set","name":"fbTimer","field":"name","expected":"fbTimer","value":"fbTimerNew"},
  {"op":"set","name":"fbTimerNew","field":"comment","expected":"Old comment","value":"New comment"},
  {"op":"set","name":"fbTimerNew","field":"initial_value","member":"PT","expected":"0","value":"250"}
]}
```

操作按顺序执行，改名后使用新名称。pidValue取本次实际AutoShop PID，不用PowerShell自身的PID。modified=true只读反馈不授权保存或丢弃，写入前由用户处理已有未保存内容。方法二初值通过工具箱中当前已显示的成员路径操作；不把根行“...”当文本编辑，也不把整条原生字符串塞入成员值。完整原生串或尚未物化的嵌套成员可用文件模式；界面自动展开任意嵌套树未实现。BOOL使用实际ON/OFF选项，其他值交正常IDE控件处理。IDE可能规范成员顺序/大小写，保存后native_initializers返回实际原生全文；完整核对成员、FBI整表及非目标源文件。已有字段不要求递归解析类型定义，无关LD/结构未解析不阻断。大FBI表的完整界面校验可能花数分钟，可按任务选择文件模式。

正常IDE改名可能立即更新并保存引用，早于FBI目标保存；工具先保护全部原生源码及登记证据，reference_updates逐文件列出前后哈希和实际名称替换数。未更新的旧引用允许保留，不证明引用完整性。若软件实际改变了未支持的关联格式/元数据，则保留备份、报告停止及现场，不伪造元数据或盲目重试。`instances_fields_saved`与`instances_fields_saved_closed`表示已保存/完整回读，不代表已编译；`instances_updated_not_saved`仍可能已有IDE更新的引用，必须检查结果清单。

s18全局FBI项目FB实例文件新增走[offline系列](offline-editing.md#全局fbi项目fb实例s18)：准确FBI目标、add/name/data_type/initial_value:null/comment，无category，空表首项/第二项及批量同格式；正文由调用者另作目标组织。新记录不复制地址，未知双表布局明确拒绝，旧实例及两侧容器保持。

s17补齐内部VAR项目FB实例的文件新增：用[offline系列](offline-editing.md#fb内部项目fb实例s17)，现有variable_operations/add，category:VAR、initial_value:null、准确登记类型名；空表及批量同格式。IDE将FB类型文本大写，工具不构造传递初始化或地址，不同步业务正文。方法二已兼容这项实际显示规则，原记录及其他字段严格保护。

s16支持严格空GVT首项/第二项：标量使用下文普通add清单，结构initial_value:null，编辑器走table-editor-edit，文件模式走offline系列。空结构dry-run不创建行或备份，selector_preflight=pending_first_default_row；实际执行先核对IDE默认BOOL行并预检真实选择器。失败可能留已知未保存行，先完整回读，不重放。仅结构表也可继续追加；不改地址/前缀，不放宽未知空布局或登记资格。

已有结构成员改名支持field=name，使用[工程级改名与关联元数据](structure-renaming.md)。正文引用由AI另改并编译；table-apply不会只写结构后留下已知旧初值成员键。

CLI 1.03补充：[关闭工程离线开发](offline-editing.md)处理已登记ST/FB增删行、FB空表首次标量/结构端口及GVT结构新增，必须采用独立offline工作目录/命令。下文旧正文或table入口的限制仍适用，不给旧build/apply添加不存在的参数，也不编辑只读variables.json。

s8明确删除走[声明删除](declaration-editing.md)的declarations-read/editor-declarations-delete或offline入口；不向本页旧编辑接口的清单添加delete。两模式不检查引用、不级联，完整性检查保留。窗口GVT读取已覆盖已观察的声明缓存/展开监视重叠布局，仍以实际窗口完整回读为准。

用户明确需要新建LiteST FB或结构时，可先检查`object-plan --help`和`object-create --help`，由软件正常界面创建，再走已登记对象编辑。计划要求完整工程/PID、名称、初始source-file或members-file、新output；只有显式save-project才保存工程登记。先plan再按计划create，失败可能已创建部分对象，不重放。s22未知HCPP可按[独立项目登记基线](project-registration.md)关闭捕获后显式给object-plan，object-create自动绑定plan内receipt；默认strict不变，旧正文registration-receipt不能授权创建。创建结果requires_project_registration_refresh时须正常关闭后直读HCP重捕；已执行save-project不循环保存或重建。捕获不自动关开、编译或操作PLC。

整理方式：AI 根据现有表与变量适配整理  
当前状态：限定操作；不把读到类型等同能写该类型  
最后更新：2026-10-29

所有示例沿用SKILL.md已设置的绝对路径和用户准确对象名。执行前读取当前表/正文/原生基线；从结果选取实际行，不把示例名称当目标。默认不保存，`--save`才保存，`--close`需配保存；dry-run不能自动打开标签。真实写入需已有用户授权且`--experimental`，每步检查结果。

## 方法一库与LD实例（s21限定验收）

目标宿主仍为已登记LiteST FB，全局实例为已识别严格FBI；LD只是被引用的类型，不编辑其图形。先按[offline系列](offline-editing.md)关闭目标工程、export冻结基线，再对以下changes.json执行check/build/apply。`ExampleLadderFB`替换为直接HCP中的准确登记原名称；s21已提供这些格式，先确认实际安装版本支持。

```json
{"schema":1,"targets":[
  {"file":"Controller.FB","variable_operations":[
    {"op":"add","name":"fbRiseFile","category":"VAR","data_type":"TRIG.R_TRIG","type_kind":"function_block","initial_value":null,"comment":"Library FB"},
    {"op":"add","name":"fbLadderFile","category":"VAR","data_type":"ExampleLadderFB","initial_value":null,"comment":"Registered LD FB"}
  ]},
  {"file":"Instances.fbi","variable_operations":[
    {"op":"add","name":"fbRiseGlobalFile","data_type":"TRIG.R_TRIG","initial_value":null,"comment":"Library FB"},
    {"op":"add","name":"fbLadderGlobalFile","data_type":"ExampleLadderFB","initial_value":null,"comment":"Registered LD FB"}
  ]}
]}
```

VAR add可选`type_kind:"function_block"`是调用者明确选择原生256声明种类；点限定库FB用此字段区分于结构，省略时保持既有解析规则。它不证明库存在，也不要求工具递归证明业务依赖。已知标量/结构与显式FB种类矛盾仍拒绝。FBI天然FB，不接受type_kind或category；LD引用按直接HCP准确类型身份处理，不解析图形。

两类初值均显式null，生成空原生默认串，不复制/推算布局和地址；VAR原生类型文字大写，FBI保持请求原名称。`instance_type_choices`报告`registered_ld`或`explicit_request`，`library_existence_checked=false`且`compile_pending=true`。工程登记和可读文件哈希仍冻结，外部安装库不宣称已解析或冻结；库存在性、引用和语义交调用AI及AutoShop编译。正文和多文件修改由调用AI显式组织，备份、候选重建、完整回读及非目标保护保持。

该s21样本10条记录与3份整文件exact，正式单项/批量check/build/apply通过且仅目标变化；重开独立分类3个新FBI flags 0→256、其他49源exact，完整读表、组合及恢复0错误编译通过。s21已发布，历史验收仍不能替代调用者本次工程编译。

## FB/FC内部变量

```powershell
python -B $bridge editor-read --project $project --program $program --open --output "$artifacts/variables-before.json"
python -B $bridge editor-variables --project $project --program $program --changes "$artifacts/variables-changes.json" --expect-sha256 $nativeHash --experimental --save
```

`$nativeHash`取该目标最新native_sha256。操作JSON含schema=1与operations，最多32项。以下set的expected取真实原注释；新增名/类型必须依据当前工程，不能跳过依赖检查。

```json
{"schema":1,"operations":[
  {"op":"set","name":"ready","field":"comment","expected":"Original","value":"Updated"},
  {"op":"add","name":"iExampleInput","category":"IN","data_type":"INT","initial_value":"0","comment":"Input"}
]}
```

- FB：已有注释/BOOL/INT/DINT标量初值限定set；VAR/IN/OUT新增BOOL/INT/DINT，初值字符串。INOUT可新增这些标量；IN/OUT/INOUT可新增项目结构，内部VAR可新增项目结构或项目FB实例，复杂类型initial_value必须显式null，交给IDE默认初始化。平面BOOL/INT/DINT结构支持全空、全非空及混合成员注释，详见下节。宿主须为已支持LiteST FB，不能用此入口直接修改LD宿主。
- s20方法二可引用准确登记的LiteST/已识别LD项目FB，以及真实类型选择器中的点限定库类型，例如`TRIG.R_TRIG`。冻结准确根定义身份及可读定义文件哈希，不递归证明成员、引用或业务类型使用正确。真实选择器须准确唯一命中；方法二未登记单段库名及未知原生布局仍未实现。方法一库/LD的s21用法见上节，不向editor-variables清单加入type_kind。
- 内部VAR选择器未读取类型分类，未登记点限定名称先标`ide_resolved`，不预断为FB。保存后只接受原生64（结构）或256（FB），核对实际名称/类型文本、VAR类别和已知默认字段；结果`named_type_resolution`与备份`native_added_variables.json`记录实际类型及初值。未保存状态仍待原生回读，不能据此报告已确认FB类型。
- 空表或仅有复杂声明的非空表，可在备份后创建并核对准确默认行，再延后类型选择器预检；有可用标量行时先预检。dry-run不创建行。失败可能留下已知未保存行，先回读现场，不盲目重放。
- FC：独立六列表，没有初值/保持列；已有注释set，VAR/IN/OUT/INOUT的BOOL/INT/DINT新增initial_value必须null。s11支持空表首项：备份后核对默认VAR/BOOL六列行，再预检类型/类别选择器。失败可能留已知未保存首行，停止、回读，不保存或重放。dry-run不创建行，selector_preflight=pending_first_default_row表示仍待真实预检。复杂类型、返回类型、FCI和新建FC不开放。不要把FB示例字符串初值套给FC。
- 文件export的variables.json只读；FB/FC离线编辑改走offline系列，FC支持标量add或独立delete，不混用add/delete。s22另支持下节限定source_file正文路径，保留完整旧行表，不制造新LF表。不能修改只读快照充当写入接口。整表、正文、原记录和引用类型哈希保护保持，保存前备份，保存后原生/窗口核对。新增INOUT后的调用实参由AI按需求修改，工具不自动绑定。

库/LD引用沿用上面的editor-variables命令及同一JSON格式。以下`ExampleLadderFB`为合成占位，必须替换为本次工程已登记LD功能块的准确名称；`TRIG.R_TRIG`也须在本机真实选择器中存在，不硬编码软件库清单。

```json
{"schema":1,"operations":[
  {"op":"add","name":"fbRise","category":"VAR","data_type":"TRIG.R_TRIG","initial_value":null,"comment":"Rising edge"},
  {"op":"add","name":"fbLadder","category":"VAR","data_type":"ExampleLadderFB","initial_value":null,"comment":"Registered LD type"}
]}
```

上述新增不自动更新正文或绑定参数，调用AI显式组织正文，再交编译。s20已完成限定组合重开、完整回读及组合/恢复0错误编译，保存状态与编译结果仍分别报告。

## FC文件正文（s22限定profile）

使用原offline-export/check/build/apply/restore及`{"schema":1,"targets":[{"file":"CalcDemo.FC","source_file":"CalcDemo-candidate.st"}]}`，正文文件相对changes.json解析，为UTF-8无BOM。可仅修改正文，不需要把变量声明塞进正文或编辑只读快照。

输入须是已识别完整FC，正文行数与行表记录数匹配，三个行字段均属全零profile。仅改正文长度和正文数据，完整保留旧行表、声明及其他边界；不按新LF数生成/补零/删减行记录。已验2→4行输出正文4/行表2，独立匹配4行输入删至1行输出1/4；两份候选与正常IDE整文件exact。

输出可滞后，不能称行表已刷新或直接续用旧工作目录。正常IDE处理后重新读取/export，只有真实取得匹配基线才继续文件路径；不保证一次保存会归一化行表。输入原本滞后、compact/未知布局或非零行字段拒绝，`offline_unsupported_fc_row_metadata`含line、row_index、field、value、byte_offset、profile及reason（计数不匹配含expected）。不要清零或压成单行绕过；旧文件build/apply限制保持。

同一既有empty02副本已完成正式FC声明、上述FC文件候选及空FBI两项组合，2026-10-29 21:03:55编译0错误；第三项追加与恢复/打包仍在进行，s22尚未发布。HCP被IDE锁住而需窗口声明编辑时，另按[项目登记基线](project-registration.md)显式绑定；offline文件写入仍先关闭工程并使用自己的直接HCP基线。

## 结构/GVT双模式

```powershell
python -B $bridge table-export $tableNative --workspace $tableWork
python -B $bridge table-check $tableWork
```

只编辑新工作目录changes.json，table.json/original.native/manifest只读。set示例：

```json
{"schema":1,"operations":[
  {"op":"set","name":"ready","field":"comment","expected":"Original","value":"Updated"}
]}
```

结构成员add只有op/name/data_type/comment；GVT新增标量还需initial_value字符串。普通BOOL/INT/DINT可新增，BOOL用ON/OFF，INT/DINT用规范十进制；结构定义没有初值/保持/地址。方法二的空/非空GVT还支持已登记非空扁平结构，initial_value必须null；方法一结构新增走offline系列，旧table-check/build/apply仍不接受结构新增。已有初值set只限支持的标量，旧接口不能改已有名称/类型/保持/地址或删除。

s20平面BOOL/INT/DINT结构可混合空/非空成员注释，两模式及[正规改名](structure-renaming.md)使用同一已观察默认模板。FB仅输出有注释成员的`name:=\x07comment`，是否追加`, `依据该成员在原定义中是否末项；末项无注释时可能保留尾随`, `，不能过滤后join、trim或删注释。全空注释仍为空初始化串；GVT使用其独立空串布局，不套FB语法。初值仍显式null；`=`/`#`原样保留，`(),:`等未观察注释语法、嵌套/数组及值初始化构造仍待。混合注释已完成正常保存、方法一完整候选对照、重开完整回读及组合/恢复0错误编译。

文件路径：`table-build WORK --output NEW_CANDIDATE --experimental`生成独立候选；`table-apply WORK --experimental`备份后覆盖。用户需安排重开工程加载，再编译。

编辑器路径：

```powershell
python -B $bridge table-editor-read --project $project --table $tableName --open --output "$artifacts/table-before.json"
python -B $bridge table-editor-edit $tableWork --project $project --table $tableName --dry-run
python -B $bridge table-editor-edit $tableWork --project $project --table $tableName --open --experimental --save --close
```

不用先table-apply；`$tableName`是工程中准确表名。GVT新增要求重新导出并绑定同目录全部GVT基线/集合及跨表重名，不能复制旧地址或用target重定向。地址由IDE保存/编译分配。窗口读取是声明作用域，不包含所有展开监视成员；ID/长度空值表示本次未取得，不补0、不从磁盘伪装窗口回读。

## 全局FB实例

```powershell
python -B $bridge instances-editor-read --project $project --table $instanceTable --open --output "$artifacts/instances-before.json"
python -B $bridge instances-editor-add --project $project --table $instanceTable --changes "$artifacts/instances-changes.json" --expect-sha256 $fbiHash --dry-run
python -B $bridge instances-editor-add --project $project --table $instanceTable --changes "$artifacts/instances-changes.json" --expect-sha256 $fbiHash --experimental --save
```

FBI哈希取当次读取；清单schema=1/operations，initial_value必须null，不带category。支持已观察非空11列表或严格空FBI profile。s20方法二支持准确登记的LiteST/已识别LD项目FB和点限定库FB；FBI使用自身FB专用选择器，须准确唯一命中。根定义身份、可读文件哈希、跨GVT名称及完整表保护保留，不要求递归证明业务布局。无关GVT未解析时保护其可读文件哈希，不阻断已支持FBI目标。

```json
{"schema":1,"operations":[
  {"op":"add","name":"fbRiseGlobal","data_type":"TRIG.R_TRIG","initial_value":null,"comment":"Rising edge"},
  {"op":"add","name":"fbLadderGlobal","data_type":"ExampleLadderFB","initial_value":null,"comment":"Registered LD type"}
]}
```

`ExampleLadderFB`须替换为本次已登记LD类型；方法二库名也取真实选择器。s18文件模式项目LiteST FB新增见[offline系列](offline-editing.md#全局fbi项目fb实例s18)，方法一库/LD的s21格式见本页上节。方法二未登记单段库名、任意容器构造仍待。删除改走独立声明入口，已识别FBI原件可backup/restore；严格profile可两模式删空。空表dry-run返回selector_preflight=pending_first_default_row，不创建行/备份；真实执行先备份、核对IDE默认首行，再预检选择器。失败可能留已知未保存行，先回读，不重放。未知HCPP的s22独立项目基线见[登记说明](project-registration.md)，不拿旧正文凭据绕过。

FBI新增逐格操作读取新行完整11列，并核对全部声明名称、计数及唯一ID；保存前和保存后仍完整读取整表，不以局部页冒充完整回读。新增入口允许区分界面分配预览与原生地址，结果分开报告：

- `allocation_preview.before/after_save`列出对应时点UI与原生地址差异；`scope=not_saved_native_allocation`表示尚无获准的旧原生地址写入差量，不代表预览已写入文件。
- 若IDE保存时实际更新旧地址，只有已知地址字段的4字节精确等于写前冻结完整UI地址、且该记录其余字节全部保持，才接受。更新逐项列在`native_allocation_updates`，scope变为`editor_preview_with_native_updates`；这与仍存在的显示预览差异分开处理。
- flags、类型、初值、注释、记录长度或其他旧记录字节变化仍停止；没有上述显式冻结预览的其他入口保持严格原记录检查。不透明容器差量另报，不生成或改写未知字节。

库/LD正常保存、重开完整回读及组合/恢复0错误编译已限定验收；1623项回归通过（1项主机权限跳过）。以后加载/编译改变原生文件须重新读取、导出及获取哈希，不沿用旧工作目录。

## 系统定义及受限新建

系统表只读：`system-variables-read --project PROJECT --definitions-dir USER_INSTALL_XML_DIR --table TABLE --limit 20`；或用`--type-name TYPE`/`--search TEXT`/`--offset N`有界查询。需要用户实际安装XML和工程型号，SVT占位不是空GVT，结果不是PLC在线值，不推算未知地址单位。

新建LiteST需用户已从“程序块”打开正常对话框。`object-dialog --project PROJECT`读dialog_sha256，再`object-create-st --project PROJECT --name ExampleTask --source-file INITIAL_SOURCE --expect-dialog-sha256 HASH --experimental`。初始源码UTF8非空，最多1000行，名称ASCII字母开头、字母数字下划线1..59字符；软件可能自动加SBR_，以actual_name/target为准。创建和首次保存前分别备份，`st_created_saved`或`st_created_pending_registration`不等于编译；后者须处理真实工程保存，不重复创建。完整CLI现场另建尚待验证，不作为首次冒烟默认任务。
