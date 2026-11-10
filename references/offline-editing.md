# 关闭工程后的离线编辑

## 关闭工程新建 LiteST FB

保存并关闭整个工程。`offline-fb-plan` 从直接 HCP 和 `folder.txt` 识别已观察的平面 FB 根目录，核对重名和现有文件，生成绑定全工程文件哈希的计划。`offline-fb-create` 使用该计划与实际摘要创建空白 FB。可在规划时加 `--comment '一行注释'`，工具会生成 `(* 一行注释 *)`。

```powershell
$plan = python -B $bridge offline-fb-plan --project $project --name FB_PressCycle --output "$artifacts/fb-plan.json" | ConvertFrom-Json
python -B $bridge offline-fb-create --plan-file $plan.plan_file --expect-plan-sha256 $plan.plan_sha256 --backup-root "$artifacts/fb-backups" --experimental
```

`offline_fb_created` 且 `pair_verified=true` 表示原生 FB、`folder.txt` 和直接 HCP 已完整回读。计划和备份放在工程外。应用时先备份两个登记文件，再写入 FB、树目录和 HCP。写入期间持有独占句柄，HCP 最后写。`partial` 时检查 `landed`、备份和 `receipt`。若登记失败，工具尝试通过仍独占的句柄恢复原登记，保留已创建的 FB 供核对。强制中断时以写前 `intent.json` 和实际文件为准。

资格限于 AutoShop V4.11.0.5 已观察的 UTF-16LE HCP、连续文件登记号、平面 FB 根目录及 LiteST 记录。未知目录布局、重名、被占用工程和并发修改会停止。创建后重新执行 `offline-export`，即可通过现有流程追加声明和写正文。空白 FB 的首次文件正文写入支持一行，生成正常首行保存所观察到的一条零元数据记录。

## 含数组成员的结构变量

通过下方 `offline-export`、`offline-check`、`offline-build`、`offline-apply` 向已登记 GVT 增加普通结构根。使用准确登记的结构名和 `initial_value:null`。本例的三个数组成员由结构定义自身提供，原生 GVT 新记录只引用 `HMC_PtpIn`，默认初值为空，地址由 AutoShop 处理。

```json
{"schema":1,"targets":[{"file":"变量表.gvt","variable_operations":[{"op":"add","name":"gAxisIn_Z","data_type":"HMC_PtpIn","comment":"","initial_value":null}]}]}
```

## FC已有类别与数值类型

FC现有数值声明的两入口支持明确 `set category`／`set data_type`。目标须在输入中已存在，原类型 CString 为空，类型为 BOOL／INT／DINT／REAL、类别已识别；新类别限定 VAR／IN／OUT／INOUT，新类型限定上述四种。逐操作核对 `expected`，只改相应 DWORD，保留另外两尾未知值、名称、注释、其他记录及完整正文／行表／外壳。正常界面独立样本为 VAR→OUT 和 INT→REAL，其他组合仅有合成检查；正式验证及交付状态见[本批报告](validation.md)。

BYTE／IP／STRING、ARRAY、结构、FB实例换型、非空类型 CString 及未知代码不属于本次 set；既有新增能力保持。不能 set 本批才 add 的行，不能附加初值或保持字段。正文和调用实参不自动同步，语义交 AutoShop 编译；文件方式关开工程后加载，编辑器保存后重新捕获登记凭据。名称、返回类型／FCI及新建FC仍待。

```json
{"schema":1,"targets":[{"file":"CalcDemo.FC","variable_operations":[
  {"op":"set","name":"enabled","field":"category","expected":"VAR","value":"OUT"},
  {"op":"set","name":"counter","field":"data_type","expected":"INT","value":"REAL"}
]}]}
```

沿 `offline-export` → `offline-check` → `offline-build` → 显式摘要 `offline-apply`，不修改只读快照。示例名称须来自准确登记对象；set不附 `initial_value`，新增 add 仍要求 `initial_value:null`。

## s31限定原生范围与门禁证据

FC普通已登记命名结构声明（code64），以及FB一／二维结构ARRAY中更深code64成员默认、含ARRAY成员子结构的默认表示。FC沿独立三尾记录，所有新增明确null，无FB式初值／保持字段；FB结构ARRAY沿独立value／comment模板，code64继续处理准确已识别子定义，code128成员省略并保留原位置分隔符，不生成其内部元素默认值。普通结构的根注释模板仍独立，GVT／STRU普通根不是这种默认生成。

准确非空定义、真实选择器、全部可读定义哈希、未保存内容、唯一备份、CAS及旧记录／正文／不透明字节和完整回读保护保持。FC／GVT／STRU普通根只核准确身份，不递归证明成员业务合法性；FB只遍历实际code64默认依赖，省略的ARRAY不追业务元素图。FB递归格式以工作栈、活动类型路径及共享UTF-8预算实现；循环、错名／缺失／空定义、未知标量或注释语法拒绝。嵌套空注释关闭后不加07，标量空注释仍保留07；预算沿现有65533字节CString／容器边界，不是PLC容量规则。helper缺省及既有非递归模式、sharedflat和结构改名不扩。三维、IEC上下界、FB元素ARRAY、任意显式复杂初值、ARRAY成员内部元素默认构造、未知宿主记录、FC返回类型／FCI／FC中FB实例／通用新建FC仍另待。

本轮限定原生验收、两模式持久回读、组合与恢复0错误编译、关闭观察及最终67／59／192精确恢复完成；最终完整软件与本地包交付以包外实际回执为准。

本段记录2026-11-01.s31／CLI1.03原生门禁完成的构建前时点；完整软件、资源数量、manifest与ZIP结果由随后包外实际回执提供。最终软件数字／ZIP结果由包外回执补充；不安装、创建Git提交／标签或远端发布，安装／公开仍s24。35公共签名保持，合成契约案例不替代原生验收。[本轮证据](validation.md)。

## s29历史本地候选：FB嵌套结构及含ARRAY成员结构默认

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

### 默认、特殊注释与请求表达

FB引用准确登记的`ByteIpData[2]`或`ByteIpData[2,3]`时，四类别均明确`initial_value:null`。结构ARRAY中BYTE成员的已观察默认为`0`，IP为`192.168.1.0`；这些值由受保护的默认构造生成，不填成顶层字符串。普通结构沿独立成员注释模板，不套用ARRAY的值/注释模板。

结构定义中正常IDE保存的成员注释可包含已观察括号、逗号和冒号；原生编码后的comment用于相应普通/ARRAY模板并保留原字节，不解码后再写回。原生03/04/05属于本批新增已观察成员注释profile，06沿既有profile；这与FB ARRAY变量自身注释的01/02/05显示映射不同。FB新增仅提交`initial_value:null`，自动读取已冻结定义的raw注释并沿已验模板生成，不手拼复杂初始化串。既有STRU注释编辑仍沿导出raw的`expected`/`value`契约；适配器负责可见转换及保存后raw核验，调用者不自行归一化导出值。未知literal profile继续拒绝。含实际字面分隔符的未识别原生comment、未知控制字符、TAB或未配对CR/LF仍拒绝；不提供通用注释编码器，不推定FC/GVT或其他未知布局。

普通结构隐藏初值可能规范成员大小写并省略部分原生内容；原生全文、隐藏值和预览分别记录，仅在完整限定profile下核对，不清洗raw快照来制造相等。

```json
{"schema":1,"operations":[
  {"op":"add","name":"localData","data_type":"ByteIpData[2]","category":"VAR","initial_value":null,"comment":""},
  {"op":"add","name":"inputGrid","data_type":"ByteIpData[2,3]","category":"IN","initial_value":null,"comment":""},
  {"op":"add","name":"outputData","data_type":"ByteIpData[2]","category":"OUT","initial_value":null,"comment":""},
  {"op":"add","name":"inoutGrid","data_type":"ByteIpData[2,3]","category":"INOUT","initial_value":null,"comment":""}
]}
```

示例名称是合成占位，须替换为准确登记的真实定义。方法二使用operations清单；文件模式将同样操作放入schema1/targets对应FB的variable_operations，再执行offline-export/check/build/apply。不修改只读导出表，不混合删除与新增事务。

本批范围及分阶段证据见[结构ARRAY默认与特殊注释报告](validation.md)。

## s27历史：BYTE/IP数组与普通扁平结构引用

s27历史本地候选为2026-10-31.s27／CLI1.03，扩展`BYTE[2]`、`BYTE[2,3]`、`IP[2]`、`IP[2,3]`所代表的一／二维ARRAY，沿FB四类别、FC四类别、结构直接成员及GVT既有两模式入口；另补含BYTE/IP成员的普通扁平结构引用。正常保存／整文件对照、正式两模式适当空／非空保存及跨会话完整回读已完成；共同正文18:02:05编译0错误（9612行），原代码18:23:14恢复编译0错误（9588行），相应严格回读、FBI71及关闭观察分别留证。最终67原件／59源码原哈希、192集合已核，5项生成差量单列；原失败与补充资格不追改成功。最终软件和完整包结果以包外本批回执为准，本轮仅本地，不安装或远端发布，实际安装／公开仍s24。证据见[本轮报告](validation.md)。

FB、FC、GVT数组新增均传`initial_value:null`，结构成员不带该字段；不填BYTE或IP直接标量的默认值。FB/FC/结构成员保存code128及完整类型文本；GVT数组使用独立元素码、总元素数和维度尾字段，初值为空、地址未分配交IDE处理，不能把类型文本或显示位长当原生布局。方法二走真实ARRAY对话框，并核完整表及实际默认字段。

已有扁平结构可含BYTE/IP成员，普通FB VAR/IN/OUT/INOUT及GVT引用仍传null并冻结准确根定义。FB沿实测成员注释模板，GVT普通结构原生初值为空；这些默认格式不扩张到含新成员结构的ARRAY、嵌套结构或显式复杂初值。三维、显式上下界、FB元素及未知布局仍另待。

FB code128 ARRAY注释的实际显示与新增保存核验支持已观察的方括号、逗号原生转义；原生`comment`仍保留raw，旧记录仍逐字节保护。此显示映射不推定FC／STRU／GVT或未知控制字符，也不是通用comment-set编码器。EtherNet/IP导出等工程语义限制仍由AutoShop编译检查，工具不修改网络配置或猜测分配地址。

```json
{"schema":1,"targets":[
  {"file":"Logic.FB","variable_operations":[
    {"op":"add","name":"byteSamples","data_type":"BYTE[2]","category":"VAR","initial_value":null,"comment":"Byte array"},
    {"op":"add","name":"ipGrid","data_type":"IP[2,3]","category":"OUT","initial_value":null,"comment":"IP array"},
    {"op":"add","name":"packetInput","data_type":"FlatPacket","category":"IN","initial_value":null,"comment":"Existing flat definition"}
  ]},
  {"file":"Globals.gvt","variable_operations":[
    {"op":"add","name":"globalByteGrid","data_type":"BYTE[2,3]","initial_value":null,"comment":"Global array"},
    {"op":"add","name":"globalPacket","data_type":"FlatPacket","initial_value":null,"comment":"Existing flat definition"}
  ]}
]}
```

示例`FlatPacket`须为当前工程已有的准确扁平结构定义，不由示例自动创建。其定义先保存并重新冻结，再创建引用；原记录／正文／不透明字节、唯一备份、全部哈希、完整回读和未保存内容保护保持。

## BYTE/IP直接声明

此前已完成的本地s26 / CLI1.03范围如下。FB四类别、FC、STRU直接成员及GVT的BYTE/IP两模式新增已完成限定原生验收：正常保存整文件对照、适当空/非空正式保存、跨会话完整回读、组合及恢复编译0错误、关闭观察和精确事件审计分别留证。编译器观察到的地址/FCI差量与工具写入分开记录，67原件及59源码已恢复，192集合保持，生成差量单列。该批最终软件与包结果由其包外回执记录，已完成s25归档保持，实际安装/公开仍s24。阶段及证据见[s26报告](validation.md)。

原生类型码为BYTE 8192、IP 4096；IDE默认分别为`0`与`192.168.1.0`，GVT显示位长分别为8/32。FB VAR/IN/OUT及GVT提供明确字符串初值，保留原文交AutoShop编译；FB INOUT及全部FC提供JSON null，STRU成员没有独立初值字段。IP编辑器使用已观察的ATL文本控件，完整字符串回读，不把IP初值转换为推算地址。s26仅含直接声明／成员；本轮ARRAY与普通扁平引用范围见页首，含新成员结构ARRAY默认及未知复杂布局仍另待。

方法一沿原offline流程使用以下targets；方法二FB沿editor-variables使用对应`schema:1,operations`，STRU/GVT沿table-editor使用对应changes.json。文件名替换为已准确登记对象，不因示例创建容器：

```json
{"schema":1,"targets":[
  {"file":"Controller.FB","variable_operations":[
    {"op":"add","name":"localByte","data_type":"BYTE","category":"VAR","initial_value":"165","comment":"Byte value"},
    {"op":"add","name":"peerIp","data_type":"IP","category":"INOUT","initial_value":null,"comment":"IP reference"}
  ]},
  {"file":"CalcDemo.FC","variable_operations":[
    {"op":"add","name":"inputIp","data_type":"IP","category":"IN","initial_value":null,"comment":"IP input"}
  ]},
  {"file":"Data.stru","variable_operations":[
    {"op":"add","name":"statusByte","data_type":"BYTE","comment":"Direct member"}
  ]},
  {"file":"Globals.gvt","variable_operations":[
    {"op":"add","name":"globalIp","data_type":"IP","initial_value":"10.23.4.5","comment":"Explicit IP"}
  ]}
]}
```

原记录、正文、不透明字节、基线/并发哈希、唯一备份及完整回读保护保持；不因新类型码已识别就放宽未知宿主布局，也不重放已消费的验证步骤。

s25历史阶段说明：其限定原生验收已完成，当时本地候选修订为2026-10-31.s25；最终软件校验结果以包外交付回执为准；当前实际安装/公开仍为s24，不安装、不云端发布，不能因同为CLI1.03而向旧安装提交ARRAY请求。下方s24及更早已交付功能保持。

## ARRAY新增（s25本地交付准备）

沿原offline-export/check/build/apply流程及`schema:1`的targets/variable_operations新增，不修改只读variables.json。四宿主数值builtin、STRING默认128/20及已登记结构元素一/二维已有16组正常保存配对、42条新增记录的整文件exact对照。两模式空/非空正式保存、完整持久回读、候选编译与最终恢复已有证据；本轮另完成候选后台关闭及同条件真实F7/鼠标关闭对照，最终恢复编译0错误、67原件/59源码exact、192集合保持，仅Temp/EIPIns.foid生成差。GVT原9项公共批超时和限定续作分开记录，不把后续成功追认为原批成功。受测环境禁用Computer Use插件、主Windows后端缺席而Swift仍在，历史vsflex/MFC错误保留，根因未定，不宣称所有客户端或环境均已修复。当前本地候选为2026-10-31.s25/CLI1.03，完整性以91文件清单及check_bundle为准，最终软件校验结果由包外回执记录；未安装或公开发布。

以下是开发请求格式，文件名须替换为当前准确登记对象，FlatData须为已有准确登记/定义哈希的结构；不因示例创建新对象，不在同批改正在引用的结构根后仍按旧定义生成数组，不把FB数组默认模板套为GVT默认串：

```json
{"schema":1,"targets":[
  {"file":"Controller.FB","variable_operations":[
    {"op":"add","name":"samples","category":"VAR","data_type":"INT[3]","initial_value":null,"comment":"Numeric array"},
    {"op":"add","name":"labels","category":"VAR","data_type":"STRING<20>[2,3]","initial_value":null,"comment":"FB text array"},
    {"op":"add","name":"states","category":"VAR","data_type":"FlatData[2]","initial_value":null,"comment":"Registered structure array"}
  ]},
  {"file":"CalcDemo.FC","variable_operations":[
    {"op":"add","name":"requests","category":"IN","data_type":"BOOL[2]","initial_value":null,"comment":"FC numeric array"},
    {"op":"add","name":"inputStates","category":"IN","data_type":"FlatData[2,3]","initial_value":null,"comment":"Registered structure array"}
  ]},
  {"file":"Data.stru","variable_operations":[
    {"op":"add","name":"matrix","data_type":"INT[3,2]","comment":"Array member"},
    {"op":"add","name":"states","data_type":"FlatData[2]","comment":"Registered structure array member"}
  ]},
  {"file":"Globals.gvt","variable_operations":[
    {"op":"add","name":"globalMatrix","data_type":"INT[3,2]","initial_value":null,"comment":"Global array"}
  ]}
]}
```

新复杂默认`initial_value:null`，不写`"0"`或`"..."`；STRU成员没有category/initial_value。ARRAY一维为`Element[n]`、二维为`Element[n,m]`，不写`Element[n][m]`或自行换算未观察的显式上下界。STRING默认128保留原生`STRING<128>[2]`，UI可显示`STRING[2]`；明确20二维为`STRING<20>[2,3]`，原生容量及UI别名分别核对。结构元素用已验根定义生成宿主默认值，FB数组的值/注释模板不同于普通结构变量；不手拼初始化串、不递归证明业务引用。未知组合具体报告未实现，不因旧白名单永久禁止，也不借已有读取能力放行未知新目标。

正文、引用和多文件修改由调用AI用原source_file机制显式组织，不自动同步或证明业务语义。旧记录/不透明字节/正文、全部基线哈希、唯一备份、候选重建、写后完整回读及非目标保护保持；无关旧未知数组不递归阻断已支持目标。编辑器可选array_type_verification的partial/未解释字段只是精确诊断，不代表所有原生字段已核，新目标未知仍停止。方法二沿原editor-variables/table-editor-edit，字段与JSON见本页开发示例及Skill的references/data-editing.md ARRAY小节。

## 已交付范围与离线保护

s24本批补齐含REAL与规范STRING容量描述的扁平结构变量及FB VAR/IN/OUT/INOUT接口，复用既有offline系列，不新增同步业务引用的接口。正常IDE12条新记录跨3份完整保存文件与候选逐字节一致；非空正式文件和编辑器路径完整回读，显式正文修正后22:45:50组合编译0错误。两模式空表FB/GVT各两项均已正式保存、重新打开及完整回读；空表中间态保留旧引用而未编译。最终恢复和交付见[本批结构profile报告](validation.md)，各阶段不由s23历史结果替代。

s23两模式REAL/STRING直接声明的限定原生验收及恢复、完整回归、包校验、安装及发布均已完成；该版为2026-10-30.s23/CLI1.03/89文件，指定安装及GitHub953c137全文件核验一致，证据见[s23报告](validation.md)。新增JSON见下文，旧安装不能仅凭CLI1.03取得后续修订能力。

s22限定原生验收完成：新增独立显式项目登记基线与FC限定离线正文路径。未知HCPP头尾不改，基线另见[调用与失效规则](project-registration.md)；FC写正文保留完整旧行表，不重建LF行表。以下为s22既有证据：21:03:55组合0错误，第三项追加和恢复均完成；最终21:11:23及恢复21:16:23均0错误，14根原生exact、空表正式回读和干净关闭通过。

方法一库/已登记LD实例新增已完成本轮限定验收：单项及批量正式offline写入、重开9声明/74实例及全文完整回读，2026-10-29 19:49:05编译0错误；恢复原6/71项后19:52:35再次0错误并完整回读、干净关闭。59份根原生源全部与本轮起点逐字节相同，生成物差量另记，未新增工程副本。该能力随s21已交付。

s17补齐已登记LiteST FB内部VAR的项目FB实例新增，含空表首项和批量追加。使用下文原offline系列及完整保护，详见[内部实例专项](validation.md)。

s16新增严格空GVT首项/第二项：标量和已支持扁平结构复用本页variable_operations/add格式及全量保护，不新增profile开关。正常IDE保存与候选整文件匹配，实际重开回读通过，原12项加本轮5项编译0错误；见[专项报告](validation.md)。未知空布局另待；未知HCPP的默认strict不变，s22可显式使用独立项目登记基线，不靠镜像放权。

整理方式：AI 根据实现与独立副本验证整理  
历史阶段状态：s24已交付；s25本地候选的限定原生验收完成，最终软件校验以包外回执为准，安装/公开仍s24  
最后更新：2026-10-31

offline系列处理已创建并登记的ST、LiteST FB、ST型FC、结构、全局变量表和FBI实例表，不新建对象、不改HCP。保存所需修改并关闭整个目标工程，关闭FB标签不足以重载；无需退出AutoShop。输出和备份必须在工程及Skill安装目录外。当前为同步CLI和内部Python工作流，不属于service.__all__的稳定接口。

## 命令与路径

FC原BOOL/INT/DINT编码已随s11交付（[报告](validation.md)），s23已交付的REAL/STRING见下节。目标为已登记并严格可解析的ST型FC；VAR/IN/OUT/INOUT均要求initial_value:null。示例：`{"file":"CalcDemo.FC","variable_operations":[{"op":"add","name":"inputValue","category":"IN","data_type":"INT","initial_value":null,"comment":"Input"}]}`。add不与delete混用，不支持set、数组/结构等复杂类型或返回类型；s22可另带source_file，但必须满足独立正文profile。三尾字段声明记录不套FB初值/保持格式；未请求正文时完整原正文及行表保持，不靠新增变量修复旧滞后表。闭工程、直接HCP、全部基线/唯一备份和完整回读保护保持。

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

## 含REAL/STRING成员的扁平结构变量和FB接口（s24）

引用目标须为准确登记、非空的扁平结构，成员可以是BOOL/INT/DINT/REAL及具有规范容量文本的STRING；类型码和原生描述逐项匹配。STRING必须保留`STRING<n>`，不能只有2048类型码或以裸UI显示代替容量。目录不再以旧四位长度白名单决定资格；正常IDE容量样本仍为20和默认128，不保证任意容量或PLC支持。

FB四类别和GVT的结构新增都显式`initial_value:null`。FB使用已观察的成员注释模板，全空注释生成空串，混合注释按成员原位置保留分隔符；原生6/8分隔符和CRLF原样进入模板，不清洗成显示字符。GVT使用独立空原生初始化，不套FB模板，不推算或复制分配地址。CRLF的真实新增保存证据为VAR补充样本，其他类别目前为合成编码回归。ARRAY、嵌套及任意显式复杂值仍另待，未知C0、孤立CR/LF、`(),:`等初始化语法返回准确结构/成员/字段/值，不删注释或清零绕过。

以下为已登记`FlatData`的文件请求例子。目标文件、类型和变量名均须替换为本次工程的准确对象；沿本页命令在新工作目录export/check/build/apply，不能编辑variables.json：

```json
{"schema":1,"targets":[
  {"file":"Controller.FB","variable_operations":[
    {"op":"add","name":"stLocal","data_type":"FlatData","category":"VAR","initial_value":null,"comment":"Local structure"},
    {"op":"add","name":"stInput","data_type":"FlatData","category":"IN","initial_value":null,"comment":"Input structure"},
    {"op":"add","name":"stOutput","data_type":"FlatData","category":"OUT","initial_value":null,"comment":"Output structure"},
    {"op":"add","name":"stReference","data_type":"FlatData","category":"INOUT","initial_value":null,"comment":"Reference structure"}
  ]},
  {"file":"Globals.gvt","variable_operations":[
    {"op":"add","name":"stGlobal","data_type":"FlatData","initial_value":null,"comment":"Global structure"}
  ]}
]}
```

正文及引用由调用AI显式提供，需要时通过适用目标的`source_file`同批组织，或随后修改正文。全局访问的`::`及FB调用实参由调用者处理；工具不查旧引用作为新增门槛，也不据类型声明自动改业务正文。空表与非空表使用相同JSON，严格容器、定义/全部原生基线、唯一备份、候选重建、完整回读和非目标保护保持；文件写入后须正常重开加载，不能保存旧编辑器覆盖新文件。

## REAL与STRING直接声明新增（s23已交付）

沿用上述export/check/build/apply，不传profile开关，也不编辑只读variables.json。REAL和STRING是直接标量声明，继续保留原BOOL/INT/DINT规则和每种原生容器的独立布局：

| 目标 | 请求中的initial_value |
| --- | --- |
| FB VAR/IN/OUT | 显式原文字符串；REAL如`"1.250000"`，STRING默认空原生串用`""` |
| FB INOUT | null；正常IDE已观察REAL原生默认`0.000000`、STRING空原生默认串 |
| FC VAR/IN/OUT/INOUT | 一律null；FC本身没有独立初值/保持列 |
| STRU成员 | 不带initial_value或category字段 |
| GVT变量 | 显式原文字符串，不带category；地址由IDE/编译分配 |

`data_type:"STRING"`使用本机已观察默认128，等价原生参数`STRING<128>`；`STRING<20>`等明确指定容量。实际编辑器对默认128可显示裸STRING，明确20显示STRING<20>；窗口文字与原生参数分别核对，不能仅凭裸显示断言长度未设置。GVT的nBitLen是界面显示信息，不是给写入器增加的字段。

REAL候选保存调用者原文，不用Python float转换或规范化；语法、引用、容量和业务语义交调用AI与AutoShop。非空STRING正常实测为含双引号的字面，JSON要保留这些引号：`"initial_value":"\"Bridge text\""`。工具不自动添加引号或按容量截断内容；编辑器自身产生的显示/保存结果另作完整回读。

以下四个目标和名称为示例，替换为本次准确登记对象。两个类型都支持FB/FC四类别；与正常初值字段不同，INOUT/FC的null表示沿已观察默认处理：

```json
{"schema":1,"targets":[
  {"file":"Controller.FB","variable_operations":[
    {"op":"add","name":"rLocal","category":"VAR","data_type":"REAL","initial_value":"1.250000","comment":"Real local"},
    {"op":"add","name":"sLocal","category":"VAR","data_type":"STRING","initial_value":"\"Bridge text\"","comment":"Text local"},
    {"op":"add","name":"rInput","category":"IN","data_type":"REAL","initial_value":"0.000000","comment":"Real input"},
    {"op":"add","name":"sInput","category":"IN","data_type":"STRING<20>","initial_value":"","comment":"Text input"},
    {"op":"add","name":"rOutput","category":"OUT","data_type":"REAL","initial_value":"0.000000","comment":"Real output"},
    {"op":"add","name":"sOutput","category":"OUT","data_type":"STRING<20>","initial_value":"","comment":"Text output"},
    {"op":"add","name":"rReference","category":"INOUT","data_type":"REAL","initial_value":null,"comment":"Real reference"},
    {"op":"add","name":"sReference","category":"INOUT","data_type":"STRING<20>","initial_value":null,"comment":"Text reference"}
  ]},
  {"file":"CalcDemo.FC","variable_operations":[
    {"op":"add","name":"rLocal","category":"VAR","data_type":"REAL","initial_value":null,"comment":"Real local"},
    {"op":"add","name":"sLocal","category":"VAR","data_type":"STRING","initial_value":null,"comment":"Text local"},
    {"op":"add","name":"rInput","category":"IN","data_type":"REAL","initial_value":null,"comment":"Real input"},
    {"op":"add","name":"sInput","category":"IN","data_type":"STRING<20>","initial_value":null,"comment":"Text input"},
    {"op":"add","name":"rOutput","category":"OUT","data_type":"REAL","initial_value":null,"comment":"Real output"},
    {"op":"add","name":"sOutput","category":"OUT","data_type":"STRING<20>","initial_value":null,"comment":"Text output"},
    {"op":"add","name":"rReference","category":"INOUT","data_type":"REAL","initial_value":null,"comment":"Real reference"},
    {"op":"add","name":"sReference","category":"INOUT","data_type":"STRING<20>","initial_value":null,"comment":"Text reference"}
  ]},
  {"file":"Data.stru","variable_operations":[
    {"op":"add","name":"rValue","data_type":"REAL","comment":"Real member"},
    {"op":"add","name":"sLabel","data_type":"STRING<20>","comment":"Text member"}
  ]},
  {"file":"Globals.gvt","variable_operations":[
    {"op":"add","name":"grValue","data_type":"REAL","initial_value":"1.250000","comment":"Global real"},
    {"op":"add","name":"gsLabel","data_type":"STRING<20>","initial_value":"\"Global text\"","comment":"Global text"}
  ]}
]}
```

正文/调用实参由AI显式组织，需要时按原source_file机制同批提交；本接口不自动更新业务引用。新声明不复制旧分配地址或旧缓存，原记录、完整正文/行表及非目标文件继续保护。含REAL/STRING成员的扁平结构引用按本页s24独立profile处理；嵌套/显式复杂值初始化、ARRAY新增和STRING数组不由本节直接标量编码推定支持。

## FC正文增删行（s22限定profile）

使用原offline系列，不给旧build/apply加参数，不传profile开关。请求可仅改正文，也可与已支持标量新增或独立delete目标组织；add/delete仍不混用。正文是UTF-8无BOM，source_file相对changes.json解析：

```json
{"schema":1,"targets":[{"file":"CalcDemo.FC","source_file":"CalcDemo-candidate.st"}]}
```

输入必须为完整已识别FC，正文行数与行表记录数匹配，记录顺序及三个行字段均属于已观察全零profile。写入只替换正文长度和正文数据，完整保留旧行表和其他边界/声明字节；不按新LF数生成、补零或删减行记录。已观察2→4行输出为正文4/行表2，独立匹配4行输入删至1行输出1/4，两候选均与正常IDE整文件exact。

输出可能滞后，这不是已刷新行表；不能在同一旧工作目录继续下一次写入。由正常IDE处理后重新读取和export，只有真实重新取得匹配基线才继续此文件路径，不保证一次保存便使行表匹配。原本已滞后、compact/未知布局及非零未知字段拒绝，`offline_unsupported_fc_row_metadata`报告line、row_index、field、value、byte_offset、profile、reason，计数不匹配时另有expected；不要清零、压成单行或手造新行表绕过。

该s22路径已与未知HCPP显式项目基线的声明编辑、FB/结构创建及FBI追加完成组合/恢复0错误编译并交付；与s23直接声明、s24结构新增的验收分别记录，不据此扩展任意FC行元数据profile。

## 库与已登记LD实例（s21）

下例沿用本页命令，目标宿主仍为已支持LiteST FB，LD是被引用的类型，不编辑其图形。`ExampleLadderFB`必须换为直接HCP登记的准确原名称。VAR新增可带`type_kind:"function_block"`，它明确选择原生256声明种类，用于点限定库名，不证明库存在或业务正确；省略该字段保持既有类型解析规则。已知标量/结构与显式FB种类矛盾时拒绝。FBI天然是FB实例，不接受type_kind或category。

```json
{"schema":1,"targets":[
  {"file":"Controller.FB","variable_operations":[
    {"op":"add","name":"fbRise","category":"VAR","data_type":"TRIG.R_TRIG","type_kind":"function_block","initial_value":null,"comment":"Library FB"},
    {"op":"add","name":"fbLadder","category":"VAR","data_type":"ExampleLadderFB","initial_value":null,"comment":"Registered LD FB"}
  ]},
  {"file":"Instances.fbi","variable_operations":[
    {"op":"add","name":"fbRiseGlobal","data_type":"TRIG.R_TRIG","initial_value":null,"comment":"Library FB"},
    {"op":"add","name":"fbLadderGlobal","data_type":"ExampleLadderFB","initial_value":null,"comment":"Registered LD FB"}
  ]}
]}
```

两类新增均为null请求/空原生默认初始化，不生成传递布局或地址。VAR原生类型文本大写，FBI保持请求的准确原名称。已登记LD依据直接HCP类型与受保护原件识别，不要求解析图形或递归证明接口语义。库的存在性、类型使用和引用交调用AI及AutoShop编译；`instance_type_choices`区分`registered_ld`和`explicit_request`，并报告`library_existence_checked=false`、`compile_pending=true`。冻结工程登记及可读工程文件，不宣称检查或冻结外部安装库。正文及多文件组织由调用AI明确提供，完整基线、备份、候选重建和回读保护不变。

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

空表首项、第二项及非空批量同格式，每目标1–32项，最多4096声明。s18已交付精确登记并可解析的LiteST项目FB；s21扩展的库/已登记LD类型见上节。FBI原生类型文本保留准确名称大小写，不套内部VAR大写规则。新记录为空初始化、flags0和FFFFFFFF未分配地址，AutoShop加载/编译负责布局和分配，不生成传递初始化，不改类型定义或旧实例。V4.11.0.5正常加载可把新记录flags从0改为256，编译再分配地址；完整语义未解码，工具不预写256绕过。加载/编译后重新获取基线，不重放旧plan。显式复杂初值构造及其他未知字段仍另待。

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

`Controller`和`TimerBlock`仅为合成名称，必须换成实际登记对象。空表和非空表采用相同清单；每目标最多32项。新记录采用正常IDE保存已观察的类型码256、FB类型名大写形式（如TimerBlock→TIMERBLOCK）、空初始化串及VAR/不保持/未分配字段；初值必须null，显式复杂初值构造和FB类型IN/OUT/INOUT仍未实现。s21扩展的库/已登记LD类型见上节；传入准确原名称，读回大写属于原生规则，不手改类型文件或只读快照“修复”大小写。

内部实例不使用全局FBI容器，不生成地址、传递布局或结构成员初始化串；已有记录的初始化、类型拼写、全部字段和顺序原样保留。本次所需项目类型核对登记和已识别身份，库FB由调用者显式选择声明种类；全部工程文件哈希保护保持，不宣称冻结外部安装库。不因无关LD/FB未解析、引用FB中已有库/结构成员或正文尚未修完而拒绝已支持新增；不推导编译语义或自动更新调用。正文引用由调用者另改，可在同一目标显式加入source_file，多文件安排也由调用者组织，最终交AutoShop编译。

重开工程后用editor-read完整核对正文、声明及未保存状态，编译另行执行。方法二同样接受已观察的FB类型大写显示，仍逐格核对整表和备份。编译通过不表示PLC行为已验证。

## 结构注释预检修复（2026-10-26 / s9）

旧s8把ASCII `=`误列为未观察分隔符。独立副本中正常界面保存的17/31成员结构INOUT初始化串，与保留原注释的候选逐字节一致；GVT结构声明使用独立空初始化串，不套用FB语法。两种路径实际加载、完整窗口回读及全部编译0错误已分别验证。

未观察的分隔符返回 `offline_initializer_comment_unobserved`，含 `error_context`：target、operation_index、variable、category、structure、member、member_index、field、原comment、characters及character_positions、index_base=0、reason与requires。操作、成员和字符索引为0基；错误正文的成员序号为1基。普通候选格式拒绝保留 `offline_invalid_request`，补target和original_error；冲突继续 `offline_conflict`。调用方须处理未知错误码，不靠匹配错误文案判断状态。诊断可能含原注释，分享日志前审阅。

该s9记录不代表混合注释当时已支持；2026-10-28开发批次根据正常IDE样本补齐了混合空/非空注释编码，组合验收见开发报告。嵌套、数组等未知布局仍单列。ST若有非零未知行字段仍拒绝，不能清零或压成一行绕过；结构初值修复不保证完整多目标请求通过。check/build不写工程；apply/restore的独占句柄、全部基线、唯一备份、完整候选重建及回读保护未变。

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

FB add字段如上。VAR/IN/OUT的BOOL/INT/DINT初值为OFF/ON或规范十进制字符串，INOUT必须null；s23已交付REAL/STRING直接声明规则见上节。结构VAR/IN/OUT/INOUT要求已登记、非空、扁平且初值为null；成员资格现包括REAL和规范STRING容量，具体s24 profile见本页相应小节。

全空、全非空和混合成员注释采用正常IDE已观察的默认串。仅有注释的成员输出键值，分隔符按原成员位置保留；末成员为空时可能保留尾随`, `，不trim或补空注释。既有ASCII `=`/`#`和本批原生6/8分隔符、CRLF均按已观察的原生表示保留，不以显示文字覆盖。未知C0、孤立CR/LF或ASCII `(`、`)`、`,`、`:`初始化语法仍准确报告未实现；嵌套和数组另待。set仅既有注释或支持标量初值，精确字段为op/name/field/expected/value；默认已验范围不包含类别/类型修改。旧全有/全无及混合注释验收与本批新增类型的样本、组合和恢复分别记证。

开发CLI已接入FB/FC/GVT可删至空、结构保留至少一成员的明确删除：variable_operations使用op/name/expected_record_sha256三字段的delete项，不与add/set混用。按用户原则不查引用/调用/类型使用者，不因其他LD/FBI及内嵌登记未解析而阻断，不级联；对象身份、全部基线/备份、候选重建及完整回读保护保留。FB可显式附source_file修正文；s22的FC删除也可带source_file，但须满足匹配全零输入/完整保留旧行表的独立profile。FBI非空结果删除已接入CLI并实际保存验证，方法一apply/重开回读70项及恢复71项已验证，00:40:05恢复编译0错误；FBI严格profile删空已补齐，空表首项/第二项由instances-editor-add实现；限定FBI离线新增见s18段落，任意容器构造仍未实现；FB/FC/GVT删空两种模式已保存/回读验收，STRU末项菜单灰色，删除扩展分发状态以包清单为准。四目标磁盘apply/restore/reapply及重开完整回读已通过，故意保留正文引用时编译报预期未定义变量；四目标恢复后00:09:32全部编译0错误，后续00:25:28恢复编译0错误及最终窗口回读已通过，见[删除专页](declaration-editing.md)。

GVT add精确字段为op/name/data_type/initial_value/comment。结构必须initial_value:null，新记录使用真实保存profile的未分配地址FFFFFFFF，交由IDE分配，不估算地址或复制旧地址。s16严格已识别空GVT也支持BOOL/INT/DINT和上述结构首项/后续追加，完整空容器前缀保持，未分配地址不复制。跨GVT/FBI及工程对象重名拒绝。同批修改结构再新增其引用暂不支持，分批刷新基线。结构表标量add/set复用原table逻辑，add没有category/initial_value。

ST增删行支持原全零profile及s15已识别的词法折叠缓存profile（depth/header/expanded）。按相同逻辑行迁移原记录，删除行移除记录，新增/替换行用正常IDE已观察的中性记录；重建UTF8字节长度、LF+1计数及顺序索引，前缀保持。AutoShop加载/保存自行刷新词法缓存，不证明业务语法。未知值返回offline_unsupported_st_row_metadata，error_context有target、line（1起）、row_index、field、value、byte_offset、profile和reason；不清零未知字段或压成单行。滞后ST行表仍拒绝。FB沿真实IDE保存行为保留完整旧行元数据，更新正文长度和字节、重定位变量造成的嵌入边界，不伪称滞后行表已刷新。FC正文增删行另按本页s22独立profile保留完整旧行表，不能套ST迁移规则；LD写入不属于本入口，稳定旧build/apply限制保持。

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

## s30历史：普通结构成员与GVT结构根（已完成本地交付）

s30限定原生验收、最终恢复、完整软件回归和本地包交付均已完成；当前s31新增范围与门禁证据见本页顶部。


s30历史范围：源码已实现STRU新增准确登记的普通结构成员，以及GVT普通code64引用含ARRAY成员或nested成员的结构根。s30该批STRU正式范围仅为两模式的非空表追加；IDE禁止删除最后成员，不能宣称空STRU首项已验。GVT沿独立根记录profile，目标结构必须准确登记、定义可读且非空；不递归证明成员业务依赖，不推算子布局或地址，不把FB默认模板套给GVT。共享flat默认helper、结构改名及其他宿主边界保持。

STRU add只有`op/name/data_type/comment`，没有`category`或`initial_value`。GVT add另需明确`initial_value:null`，新候选原生初值为空串，flags257、地址FFFFFFFF、空device及两尾0；后续地址由IDE分配；原生初值与界面“...”及隐藏预览分开记录。文件模式只写目标原生表，不新造或修改伴随CSV、不构造复杂默认；s30该批验收观察到：非空GVT的IDE保存精确追加缺少根名及四空槽；原生GVT为0项后的本case首次IDE保存，将旧1222字节CSV重建为相同BOM／三行header及当前两新根各四空槽，共290字节，旧16组／20条空槽行未保留。两种现象均保留独立前后原像及实际回读证据；这是s30该批验收工具对实际变化的逐case审查，不是公共CLI通用CSV守卫或通用reset能力。不命名四槽、推断reset原因或由工具构造CSV；其他未知变化停止审查。

身份、未保存状态、准确选择器、全部定义哈希、并发CAS、唯一备份、旧记录／正文／不透明字段和完整原生／界面回读保护保持。s30该批限定原生验收、完整持久回读、组合及恢复0错误编译、关闭观察与最终恢复已完成；67原件／独立59源码／192文件集合全部起点SHA一致，differences=[]。原始失败、精确差量审计与只读续作分别保留。s30最终软件回归及完整本地交付已完成，实际包外回执另存，s29归档保持；仅本地，未安装或远端发布。

文件模式继续用schema1的`targets[].variable_operations`，STRU与GVT字段分别如下（名称全部为占位，须换成准确登记文件和类型）：

```json
{"schema":1,"targets":[{"file":"Owner.stru","variable_operations":[{"op":"add","name":"newMember","data_type":"RegisteredInput","comment":""}]},{"file":"Globals.gvt","variable_operations":[{"op":"add","name":"newGlobal","data_type":"RegisteredComplex","initial_value":null,"comment":""}]}]}
```

先export冻结当前工程，再check/build核候选，显式apply后重新打开工程完整回读；只看到文件写入成功不能当成IDE加载或编译通过。同批先修改结构定义再新增其引用仍不自动取得新的资格，需按既有依赖基线规则分批刷新。方法二使用同样单表operations沿既有`table_editor_edit`，不改变关开工程、编译或PLC权限。

s30[验收与交付证据](validation.md)记录实际完成结果，并导航至其规格与计划；本节是已完成批次的历史范围说明，不能代替当前工程的IDE加载或编译验证。
