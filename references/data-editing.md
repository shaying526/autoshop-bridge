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

用户明确需要新建LiteST FB或结构时，可先检查`object-plan --help`和`object-create --help`，优先由软件正常界面创建，再走已登记对象编辑。计划要求完整工程/PID、名称、初始source-file或members-file、新output；只有显式save-project才保存工程登记。先inspect/plan再用计划调用create，检查created/saved/registration/readback各阶段，失败可能已创建部分对象，不重放。严格镜像资格不满足时停止，不能拿正文registration-receipt绕过创建或类型检查。严格已识别空FBI首项/第二项可用下文instances-editor-add；新空白工程未知HCPP登记另待，不绕过资格检查。

整理方式：AI 根据现有表与变量适配整理  
当前状态：限定操作；不把读到类型等同能写该类型  
最后更新：2026-10-26

所有示例沿用SKILL.md已设置的绝对路径和用户准确对象名。执行前读取当前表/正文/原生基线；从结果选取实际行，不把示例名称当目标。默认不保存，`--save`才保存，`--close`需配保存；dry-run不能自动打开标签。真实写入需已有用户授权且`--experimental`，每步检查结果。

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

- FB：已有注释/BOOL/INT/DINT标量初值限定set；VAR/IN/OUT新增BOOL/INT/DINT，初值字符串。INOUT可新增这些标量；IN/OUT/INOUT可新增已解析项目结构，内部VAR可新增已解析项目结构或项目FB实例，复杂类型initial_value必须显式null，交给IDE默认初始化。本轮结构已验范围为扁平BOOL/INT/DINT。已有标量行用于真实选择器预检，未知/库/数组/循环依赖拒绝。
- FC：独立六列表，没有初值/保持列；已有注释set，VAR/IN/OUT/INOUT的BOOL/INT/DINT新增initial_value必须null。s11支持空表首项：备份后核对默认VAR/BOOL六列行，再预检类型/类别选择器。失败可能留已知未保存首行，停止、回读，不保存或重放。dry-run不创建行，selector_preflight=pending_first_default_row表示仍待真实预检。复杂类型、返回类型、FCI和新建FC不开放。不要把FB示例字符串初值套给FC。
- 文件export的variables.json只读；FB/FC离线编辑改走offline系列及其variable_operations，FC支持标量add或独立明确delete，新增不接受source_file，不混用add/delete，不重建正文行表。不能修改只读快照充当写入接口。整表、正文、原记录和引用类型哈希保持，保存前备份，保存后原生/窗口核对。新增INOUT后必须按真实需求修改所有调用实参，工具不会自动绑定。

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

FBI哈希取当次读取；清单schema=1/operations，每项例如`{"op":"add","name":"fbExampleTimer","data_type":"FB_Timer","initial_value":null,"comment":"Timer"}`，仅在该项目已登记且严格解析FB_Timer时有效。支持已观察非空11列表或完整严格空FBI profile；类型依赖、跨GVT重名及全表保护保留。原实例定义保持，编译后地址可能变化，须重新读取。删除改走独立声明入口，已识别FBI原件可backup/restore；严格profile的FBI可两模式删空；库实例、通用离线新增及任意容器构造仍未实现。空表dry-run返回selector_preflight=pending_first_default_row，不创建行/备份；真实执行先备份，创建并核对IDE默认首行，再检查真实类型选择器。失败可能留下已知未保存首行，先回读，不重放。新空白工程未知HCPP登记可能独立阻止入口，不拿正文凭据绕过。

## 系统定义及受限新建

系统表只读：`system-variables-read --project PROJECT --definitions-dir USER_INSTALL_XML_DIR --table TABLE --limit 20`；或用`--type-name TYPE`/`--search TEXT`/`--offset N`有界查询。需要用户实际安装XML和工程型号，SVT占位不是空GVT，结果不是PLC在线值，不推算未知地址单位。

新建LiteST需用户已从“程序块”打开正常对话框。`object-dialog --project PROJECT`读dialog_sha256，再`object-create-st --project PROJECT --name ExampleTask --source-file INITIAL_SOURCE --expect-dialog-sha256 HASH --experimental`。初始源码UTF8非空，最多1000行，名称ASCII字母开头、字母数字下划线1..59字符；软件可能自动加SBR_，以actual_name/target为准。创建和首次保存前分别备份，`st_created_saved`或`st_created_pending_registration`不等于编译；后者须处理真实工程保存，不重复创建。完整CLI现场另建尚待验证，不作为首次冒烟默认任务。
