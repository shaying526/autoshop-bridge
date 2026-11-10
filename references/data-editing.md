# 变量、结构、全局表与实例

## s33本地修订：FBI初值分页与显式成员路径

本地修订`2026-11-02.s33 / CLI1.03`：开发CLI支持工具箱初值完整稀疏分页、显式结构／FB祖先路径展开与限定标量叶编辑；公共service35签名及包外90案例保持，物理选择为显式opt-in。

仅FBI初值读取`instances-editor-initial-read`和初值编辑`instances-editor-edit`接受显式`--physical-select`；默认仍沿旧targeted选择路径。调用方可在需要时自主选择此分支：它会真实移动系统鼠标指针并单击目标声明行，具有焦点／选择与指针位置副作用，不能由普通读取请求静默启用。同一显式action可按完整声明checkpoint有界滚动到目标，准备按observe／reveal_one分次执行，每call至多一次滚动，每次双完整names／目标11列checkpoint并留真实receipt；Python最多64次reveal请求、129次prepare helper调用，必须收到真正末次observe可见回执，不补假观察；随后仍严格核前台窗口、point owner、进程／工程／目标身份、按键／修饰键未按下、未保存内容和完整CAS；最多一次输入派发，不自动重试，也不自动恢复指针。其资格仅为本机Windows与AutoShop V4.11.0.5实际已验布局，不推广其他显示／DPI／软件版本；其他adapter和默认glyph范围不扩。

读取沿`instances-editor-initial-read`，重复`--member-path`给相对于实例根的点分路径；不包含实例名前缀，不接受ARRAY索引。仅显式请求的结构／FB祖先展开；已观察名称格glyph相对偏移为第1层19、第2层32，更深自动展开待验证。示例使用调用方已核对的`$bridge/$project/$table/$pidValue`与输出目录：

```powershell
python -B $bridge instances-editor-initial-read --project $project --table $table --instance DemoInstance --pid $pidValue --physical-select --member-path input.enabled --member-path output.count --output "$artifacts/initial.json"
```

每页最多64个物理slot，完整集合读取两遍并精确比较；它不是原子快照。保留每行七字段及物理索引，只将七列全空且行／名称格高度同时为1的已识别slot作为占位；屏外有名行保留，不按INVISIBLE过滤。每页核根、表头、数量和边界，集合、路径、活动编辑控件或未知布局变化即停止。展开及选择每步最多一次派发，失败或不确定派发后不自动重试。

叶编辑沿已有`instances-editor-edit`，每项使用`field:"initial_value"`及明确`member/expected/value`。嵌套叶类型限定BOOL／INT／DINT／REAL，本批实际原生叶类型为`BOOL／DINT／INT`；原有平面标量资格保持其原边界，不据本批扩展。全部请求路径在写前预展开，逐项核完整集合、全部七字段及累计预期，保留身份／CAS／唯一备份及保存前后完整回读。正常编辑原生初值由IDE序列化，原生全文与UI值独立核对，不从隐藏预览构造或解析未知初值格式。

`--physical-select`不替代修改授权：编辑仍须显式`--experimental`，保存还须显式`--save`；这不自动关开整个工程、编译或操作PLC。逐文件和跨程序保护不承诺跨文件原子事务。本批没有新增文件模式能力或service签名。阶段结果见[验证说明](validation.md)，完整软件及ZIP结论留在包外真实回执。

## s32历史本地修订：FC已有类别与数值标量类型

本地修订`2026-11-01.s32 / CLI1.03`。FC已有声明可明确修改`category`或`data_type`：输入记录原生类型CString须为空，类型限BOOL／INT／DINT／REAL，原类别须已识别；新类别限VAR／IN／OUT／INOUT，新类型限上述四种。正常界面独立对照仅VAR→OUT、INT→REAL，其余组合仅合成检查。

文件与编辑器两模式的保存、跨会话完整六列／正文／原生回读已完成；组合编译于`2026-11-01 21:57:37`、恢复编译于`2026-11-01 22:13:13`各显示0错误／9588行。最终67份原件、独立59份源码及192文件集合和全部SHA均精确恢复，关闭观察与严格停止分别留证。FBI嵌套路径仅布局观察，尚未实现。

完整软件测试及ZIP最终结果只由随后包外真实回执提供；本段不预填测试总数、包数量或构建结论。不安装、不远端发布。阶段范围见[验证说明](validation.md)。

目标须为输入原来已有声明，逐操作精确核对`expected`；同批新增行不能随即用这两个字段修改。请求仅有`op/name/field/expected/value`，不加`initial_value`或保持字段。只替换已请求DWORD，其他两尾未知值、原名称／注释、其他记录、正文／行表和外壳保持。未知类型码／类别、非空类型CString以及STRING／BYTE／IP／命名类型／ARRAY换型均停止；不提供改名、返回类型或FCI编辑，也不做业务引用同步。

方法一在既有offline工作流的changes.json中：

```json
{
  "schema": 1,
  "targets": [
    {
      "file": "CalcDemo.FC",
      "variable_operations": [
        {
          "op": "set",
          "name": "localFlag",
          "field": "category",
          "expected": "VAR",
          "value": "OUT"
        },
        {
          "op": "set",
          "name": "counter",
          "field": "data_type",
          "expected": "INT",
          "value": "REAL"
        }
      ]
    }
  ]
}
```

方法二使用独立editor-variables清单：

```json
{
  "schema": 1,
  "operations": [
    {
      "op": "set",
      "name": "localFlag",
      "field": "category",
      "expected": "VAR",
      "value": "OUT"
    },
    {
      "op": "set",
      "name": "counter",
      "field": "data_type",
      "expected": "INT",
      "value": "REAL"
    }
  ]
}
```

示例名称与目标文件须换成当次准确身份；原variables.json保持只读。方法一闭工程并重新导出完整基线，写入后重新加载整个工程；方法二须当前会话与无未保存内容，保存后旧登记基线失效。两入口均保留并发CAS、唯一备份、全部定义冻结及完整整表／正文／原生回读；业务语义由调用者处理并交AutoShop编译检查。

## s31历史本地修订：FC普通结构与FB结构ARRAY递归默认

拟议修订`2026-11-01.s31 / CLI1.03`。本轮限定原生验收、完整持久回读、组合／恢复0错误编译、正常关闭观察及最终原件恢复完成。最终完整软件、资源数量、manifest及ZIP结果以随后包外真实交付回执为准；本段不预填这些数值。仅本地，不安装或远端发布。

FC普通已登记命名结构声明（code64），以及FB一／二维结构ARRAY中更深code64成员默认、含ARRAY成员子结构的默认表示。FC沿独立三尾记录，所有新增明确null，无FB式初值／保持字段；FB结构ARRAY沿独立value／comment模板，code64继续处理准确已识别子定义，code128成员省略并保留原位置分隔符，不生成其内部元素默认值。普通结构的根注释模板仍独立，GVT／STRU普通根不是这种默认生成。

准确非空定义、真实选择器、全部可读定义哈希、未保存内容、唯一备份、CAS及旧记录／正文／不透明字节和完整回读保护保持。FC／GVT／STRU普通根只核准确身份，不递归证明成员业务合法性；FB只遍历实际code64默认依赖，省略的ARRAY不追业务元素图。FB递归格式以工作栈、活动类型路径及共享UTF-8预算实现；循环、错名／缺失／空定义、未知标量或注释语法拒绝。嵌套空注释关闭后不加07，标量空注释仍保留07；预算沿现有65533字节CString／容器边界，不是PLC容量规则。helper缺省及既有非递归模式、sharedflat和结构改名不扩。三维、IEC上下界、FB元素ARRAY、任意显式复杂初值、ARRAY成员内部元素默认构造、未知宿主记录、FC返回类型／FCI／FC中FB实例／通用新建FC仍另待。

FC与FB均沿既有offline及editor-variables入口，明确`initial_value:null`。例如准确登记非空结构`NodeData`可用作FC普通根，`NodeData[2]`或`NodeData[2,2]`可用作FB结构ARRAY；类型存在性、原生身份与全部依赖字节须准确冻结，不把示例当默认工程。FC没有初值／保持列；FB普通结构根注释默认与ARRAY子值默认分开。

正常FC三条VAR与FB八条ARRAY有独立完整wire／手写默认对照，正式两模式空／非空及四类别另行留证。本次组合编译FCI伴随不透明三字节变化按精确前后原像单例审查并最终恢复，未将它解释为地址或增加FCI编辑能力。辅助脚本派发前失败、严格释放HCP停止与另行独立原像审查／45秒续作保留各自证据，不反写旧阶段为通过。空表声明区折叠时公共几何保护仍停止；正常展开布局并完整重读后另阶段续作，不忽略guard或宣称Computer Use恢复。UI隐藏值、显示预览与原生默认分别保留；公共签名与权限边界保持。详见[分阶段验证](validation.md)。

## s30历史本地候选：STRU命名成员与GVT普通结构引用（限定原生验收与恢复已完成）

拟议修订为`2026-11-01.s30 / CLI1.03`。三项限定原生验收、跨会话完整回读、恢复编译及最终恢复已完成：67份原件、独立59份源码和192文件集合／全部SHA均与本批基线一致；各本轮正常关闭45秒存活及精确进程事件分别留证。本段记录原生门禁完成时的状态：最终完整软件回归尚未开始，尚未构建本批包；资源数量、manifest及ZIP须由随后实际构建和包外最终回执确认，不以历史测试数或旧包清单代替。不安装、不远端发布，已安装／公开记录仍分开。范围与阶段见[分阶段验证](validation.md)。

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

## BYTE/IP ARRAY与普通结构引用（s27历史本地候选）

s27历史本地候选为`2026-10-31.s27 / CLI1.03`，仅本地校验，不安装或远端发布；s26/s25原交付及验证记录保留，实际安装/公开仍s24。具体原生、软件验证和编译结果以包外本批最终回执为准，资源数量与完整性以实际manifest和check_bundle为准。

两种模式支持BYTE与IP元素的一/二维ARRAY，在LiteST FB、FC、STRU直接成员及GVT分别沿各宿主独立profile执行；例如`BYTE[2]`、`BYTE[2,3]`、`IP[2]`、`IP[2,3]`。另支持准确登记、含BYTE/IP成员的扁平结构普通引用：FB VAR/IN/OUT/INOUT与GVT。继承s26直接标量及s25既有ARRAY范围，不重复把旧能力列为本批新实现。

新ARRAY和普通结构引用均明确`initial_value:null`；STRU成员仅op/name/data_type/comment，没有category或initial_value。FC保留独立三尾字段且没有原生初值，不由此开放FC普通结构引用。FB数值ARRAY和GVT ARRAY沿已观察空原生默认，普通结构FB注释默认与GVT空原生默认分开核对；实际隐藏值、预览及原生串各自完整读取，不从位长、预览或标量IP默认值推算数组布局。

以下使用合成名称；结构根须替换为当次准确登记、定义哈希已冻结的现有类型，不因示例创建新对象。FB的editor-variables使用独立operations清单：

```json
{"schema":1,"operations":[
  {"op":"add","name":"byteSamples","data_type":"BYTE[2]","category":"VAR","initial_value":null,"comment":"Byte array"},
  {"op":"add","name":"ipMatrix","data_type":"IP[2,3]","category":"INOUT","initial_value":null,"comment":"IP array"},
  {"op":"add","name":"resultData","data_type":"ByteIpData","category":"OUT","initial_value":null,"comment":"Registered flat structure"}
]}
```

GVT的table-editor changes.json不带category，仍明确null：

```json
{"schema":1,"operations":[
  {"op":"add","name":"globalBytes","data_type":"BYTE[2,3]","initial_value":null,"comment":"Byte matrix"},
  {"op":"add","name":"globalIps","data_type":"IP[2]","initial_value":null,"comment":"IP array"},
  {"op":"add","name":"globalData","data_type":"ByteIpData","initial_value":null,"comment":"Registered flat structure"}
]}
```

STRU直接成员没有独立初值字段：

```json
{"schema":1,"operations":[
  {"op":"add","name":"byteValues","data_type":"BYTE[2]","comment":"Byte member array"},
  {"op":"add","name":"ipValues","data_type":"IP[2,3]","comment":"IP member array"}
]}
```

FC只使用ARRAY项，保留四类别及initial_value:null。方法一把对应operations放入既有offline schema1 targets的variable_operations；删除仍独立事务，不与add/set混单。方法二沿既有正常选择器、显式保存及完整回读，不新增自动关开工程、编译或PLC权限。

含BYTE/IP标量成员的结构ARRAY默认构造、未知nested默认、三维、显式上下界、FB元素ARRAY及任意显式复杂初始化不由本批开放。保留准确类型/登记、定义哈希、未保存状态、并发、唯一备份、原记录/正文/不透明字节、完整回读和非目标保护；写出、保存、重开回读及编译分别记证。EtherNet/IP导出标签等工程配置对成员类型另有语义限制，声明格式受支持不等于所有网络对象均可编译；语义交AutoShop编译检查，不自动更改业务网络配置，也不通过猜地址、改UI映像或修改缓存绕过完整回读。

源码契约1.2.0/r38、77合成案例/35公共签名在包外维护，不在portable包内；合成验证不代替原生保存、持久回读或编译验收。

### FB ARRAY注释：原生串与界面显示

正常IDE保存FB ARRAY注释时，已观察0x01/0x02/0x05分别表示界面上的`[`/`]`/`,`。文件/原生变量快照中的`comment`保留原串，编辑器完整回读使用实际显示文本；新增保存后的核验按此限定映射比较，不改写原文件中的raw串，也不把预览填作原生内容。向editor-variables提交新增清单时，`comment`使用正常可见文本，例如`"IP[2,3] probe"`；不要把raw控制字符直接复制到编辑器请求来凑匹配。本轮仅覆盖已观察FB ARRAY读取显示与新增保存回读，不新增通用comment set转义写入规则；其他宿主、普通类型和未知控制字符不由该映射扩展。

以下s26/s25及更早内容保留各自历史范围；旧限制仅由上述明确新范围细化，旧成功不追认为s27成功。

## s26历史：BYTE/IP直接声明

该历史本地修订为`2026-10-31.s26 / CLI1.03`，不安装、不云端发布；本地s25已完成并保留历史证据，实际安装/公开仍为s24。具体原生、软件验证和编译结果以包外本批回执为准，资源数量与完整性以实际manifest和check_bundle为准。

BYTE原生类型码8192、IP4096，IDE默认分别为`0`和`192.168.1.0`；GVT位长8/32。FB VAR/IN/OUT及GVT用明确字符串初值，FB INOUT及全部FC用JSON null；FC没有原生独立初值字段，STRU直接成员没有category/initial_value。IP沿已观察ATL文本控件写入并完整回读原文，不转换为推算地址。共享descriptor不开放BYTE/IP ARRAY或含这些成员结构的默认构造，未知复杂默认串仍准确报告未实现。两模式使用各自原有清单，不修改只读变量/表快照，不新增业务引用同步。FB editor-variables及FC清单使用schema/operations；GVT table-editor使用changes.json。

```json
{"schema":1,"operations":[
  {"op":"add","name":"localByte","data_type":"BYTE","category":"VAR","initial_value":"165","comment":"Byte value"},
  {"op":"add","name":"peerIp","data_type":"IP","category":"INOUT","initial_value":null,"comment":"IP reference"}
]}
```

FC使用相同字段但全部initial_value为null；GVT不带category，BYTE/IP初值仍为明确字符串。STRU成员仅op/name/data_type/comment。方法一将相应operations放入既有offline schema1 targets中对应文件的variable_operations，继续闭工程、准确登记、全部基线和唯一备份保护；方法二仍须准确会话、无未保存内容、逐字段完整整表及保存后原生回读。

源码契约r37/73案例/35签名位于包外，不随portable包交付；限定原生验收与最终软件结果不从合成案例推定。

## ARRAY新增（开发）

本节ARRAY范围已随s25本地完整包完成限定验收，s26候选沿用；实际安装/公开仍为s24，不能仅凭CLI1.03使用本节或修改旧安装清单取得能力。沿原命令、schema1清单和工程保护，不新增业务同步接口。四宿主BOOL/INT/DINT/REAL、STRING默认128/20及已登记结构元素一/二维均取得正常保存样本；16组配对/42条新增记录已整文件exact。s25正式两模式保存、持久回读、候选及恢复编译、限定关闭对照已有历史证据；s26限定原生验收及最终软件结果见包外本批回执，不能混用批次。

`data_type`使用准确AutoShop文本，如`INT[3]`、`INT[3,2]`、`STRING<20>[2,3]`、已登记结构`FlatData[2]`。一/二维分别为`Element[n]`/`Element[n,m]`，不写`Element[n][m]`，不将未观察的显式上下界或其他语法自行换算。新ARRAY默认初始化必须显式JSON null，表示按各宿主已观察原生/IDE默认生成，不是统一写入字符串`"0"`或预览`"..."`；结构元素FB默认串可非空，与数值/STRING空默认不同。STRU成员只用op/name/data_type/comment，不带category或initial_value。

FB的editor-variables清单示例；FC沿同样schema/operations及四类别、null初值，具体类别/类型组合按本次宿主profile预检。若加入结构数组，FlatData须替换为当次已登记、准确可读的根定义：

```json
{"schema":1,"operations":[
  {"op":"add","name":"samples","category":"VAR","data_type":"INT[3]","initial_value":null,"comment":"Numeric array"},
  {"op":"add","name":"labels","category":"VAR","data_type":"STRING<20>[2,3]","initial_value":null,"comment":"Text array"},
  {"op":"add","name":"states","category":"VAR","data_type":"FlatData[2]","initial_value":null,"comment":"Registered structure array"}
]}
```

```powershell
python -B $bridge editor-variables --project $project --program $program --changes "$artifacts/array-variables.json" --expect-sha256 $nativeHash --experimental --save
```

GVT先table-export到新工作目录，再仅编辑其changes.json；结构成员用同一schema/operations，但去掉initial_value和category：

```json
{"schema":1,"operations":[
  {"op":"add","name":"matrix","data_type":"INT[3,2]","initial_value":null,"comment":"Global matrix"},
  {"op":"add","name":"labels","data_type":"STRING<128>[2]","initial_value":null,"comment":"Global text array"},
  {"op":"add","name":"states","data_type":"FlatData[2,3]","initial_value":null,"comment":"Registered global structure array"}
]}
```

```powershell
python -B $bridge table-editor-edit $tableWork --project $project --table $tableName --open --experimental --save
```

STRU开发changes.json例子（仅声明成员，不是手写初始化）：

```json
{"schema":1,"operations":[
  {"op":"add","name":"textRows","data_type":"STRING<20>[2,3]","comment":"String array member"},
  {"op":"add","name":"states","data_type":"FlatData[2,3]","comment":"Registered structure array member"}
]}
```

GVT结构元素使用准确登记根定义和独立空原生初值，正常保存样本及整文件对照已取得；不能把FB数组的值/注释默认模板套入GVT。上述FlatData均为调用者已有根定义示例，不在同批编辑正在引用的结构根后仍按旧定义生成数组。

文件模式沿[offline系列](offline-editing.md)的schema1/targets/variable_operations，不编辑只读快照；上述operations分别放入准确目标的variable_operations。两种方式是替代路径，不对同一新名称重复执行。正文/调用由AI通过既有source_file机制显式组织，不自动更新引用；语法及业务语义交AutoShop编译。

裸STRING数组采用正常长度默认128：原生完整描述保留`STRING<128>[2]`，实际UI可显示`STRING[2]`；明确20二维为`STRING<20>[2,3]`。四宿主已有各自正常样本，保存时分别核容量、维度和UI别名，不能因裸显示丢掉128、伪造容量或按预览补原生值。正常元素选择及长度流程由适配器执行；调用者按实际类型和默认值请求，不需自行操纵内部控件。结构元素按准确登记根定义生成各宿主默认值，不将FB数组的值/注释模板套为普通结构默认串或递归业务证明。

表结果可选`array_type_verification`区分verified与partial，`verified_names`列已核类型，`unverified_native_fields`带name/fields/error_code/error_context。旧未知trailer等字段明确诊断，不把未解释内容称作已验证；读取时有未解释字段可返回`displayed_fields_match_native:false`。旧记录/不透明字节和UI快照仍冻结，无关旧数组不递归阻断已支持目标；新目标元素、维度或原生profile未知时停止。写前唯一备份、旧正文/记录、哈希/并发、完整回读及非目标保护不省略；部分完成后只读确认实际状态，按已知步骤续作，不重放新增。

GVT的展开树与左侧声明缓存可能重叠。开发适配器从实际完整frame核全部根/分支、身份和source/display映射；必要字段尚未绘制时只经正常界面选中/显示后重新读取，不用磁盘字段补UI，也不复用已消费的frame授权下一次编辑。本机关闭GVT标签相关OCX故障及本批限定观察顺序见[验证](validation.md)，未宣称根治；普通编辑命令不因此获得自动关开工程或退出应用的许可。

## 含REAL/STRING的扁平结构变量与FB接口（s24）

已登记的非空扁平结构可包含BOOL、INT、DINT、REAL及具有准确原生容量描述的STRING成员。结构定义的类型码与文本逐项匹配，STRING原生文本须为规范的`STRING<n>`；工具保留容量，不将2048类型码或裸UI显示当作完整描述。容量登记已统一类型识别，不再有旧四位数字白名单；本机正常IDE实际容量样本为20和128，不保证其他容量或目标PLC均支持。

FB四类别结构新增和GVT结构新增均传`initial_value:null`，由各自已观察profile生成默认记录。FB默认模板保留成员原顺序、注释及末项分隔规则；原生6/8分隔符和CRLF不清洗成显示文字。GVT原生初值为空串，与界面隐藏预览独立，不套FB模板、不写推算地址。CRLF真实保存证据为VAR补充样本，其他类别的CRLF目前为合成编码回归。ARRAY、嵌套、任意显式复杂值，以及初始化语法中的未知C0控制符、孤立CR/LF或`(),:`仍需独立profile；错误给出结构、成员、字段和实际值。正文、引用及多文件修改由调用AI组织，旧引用不阻断正常新增或改名，不增加自动业务同步接口。

**文件模式**使用新的offline工作目录，关闭整个目标工程后按[离线命令及完整保护](offline-editing.md#命令与路径)执行export/check/build/apply。将准确文件名和本次已登记类型替换下例中的`Controller.FB`、`Globals.gvt`、`FlatData`；声明不会自动插入正文：

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

需要修改调用或引用时，由调用者另在适用目标指定`source_file`，或随后通过正文入口修改。全局名称在正文中需要`::`等作用域语法时同样由调用者组织并交编译；工具不会据声明自动推断或改写正文。

**编辑器模式**沿用`editor-variables`，从本次`editor-read`取得FB原生哈希，以新文件保存以下操作清单：

```json
{"schema":1,"operations":[
  {"op":"add","name":"stLocal","data_type":"FlatData","category":"VAR","initial_value":null,"comment":"Local structure"},
  {"op":"add","name":"stInput","data_type":"FlatData","category":"IN","initial_value":null,"comment":"Input structure"},
  {"op":"add","name":"stOutput","data_type":"FlatData","category":"OUT","initial_value":null,"comment":"Output structure"},
  {"op":"add","name":"stReference","data_type":"FlatData","category":"INOUT","initial_value":null,"comment":"Reference structure"}
]}
```

```powershell
python -B $bridge editor-variables --project $project --program $program --changes "$artifacts/flat-variables.json" --expect-sha256 $nativeHash --experimental --save
```

GVT先对准确表文件执行`table-export`，仅编辑该工作目录的changes.json；文件模式结构引用不改用旧table-check/build/apply：

```json
{"schema":1,"operations":[
  {"op":"add","name":"stGlobal","data_type":"FlatData","initial_value":null,"comment":"Global structure"}
]}
```

```powershell
python -B $bridge table-export $tableNative --workspace $tableWork
python -B $bridge table-editor-edit $tableWork --project $project --table $tableName --open --experimental --save
```

以上是两种可选执行方式，不对同一名称重复运行。空表及仅有复杂类型的表沿既有默认BOOL行与延后选择器预检；出现部分修改或未知状态先完整读取实际缓冲，按已完成步骤续作，不重放整批。身份、定义/原生哈希、未保存内容、唯一备份、完整回读及非目标保护保持。本修订的实际样本、组合编译和恢复范围见[验证记录](validation.md)，不把文件候选或合成测试当本次工程已编译。

## REAL与STRING直接声明新增（s23）

s23已交付2026-10-30.s23/CLI1.03/89文件，完整回归、包校验、指定安装及GitHub953c137逐文件一致。先核实际skill_revision与bundle_verified；同为CLI1.03不表示旧安装具有后续修订能力。

REAL和STRING沿用本页原命令及清单，不新增专用写入入口。文件模式用[offline系列JSON与完整保护](offline-editing.md)，编辑器用editor-variables或table-editor-edit；下表两种模式共用：

| 目标 | 类别与initial_value |
| --- | --- |
| 已登记LiteST FB | VAR/IN/OUT显式传原生初值字符串；INOUT必须null，由IDE已观察默认生成：REAL为`0.000000`，STRING为空原生串 |
| 已登记ST型FC | VAR/IN/OUT/INOUT均传null；FC没有初值/保持列 |
| 结构成员 | 仅op/name/data_type/comment，不带category或initial_value |
| GVT声明 | 显式初值字符串，不带category；空原生初值用`""` |

`data_type:"STRING"`采用本机正常定义字符串对话框的默认容量128，原生为`STRING<128>`；`STRING<20>`等明确容量使用同一描述识别。默认128的真实UI可显示裸STRING，明确20显示STRING<20>，保存核对分别保留真实UI和原生参数，不能据裸显示丢掉容量。工具不推算地址，也不把GVT的nBitLen显示当作可写原生字段。

STRING正常原生实测容量为20和默认128，不代表所有容量均已验。

文件候选对REAL初值如`"1.250000"`逐字保留，不用Python float格式化；编辑器对IDE显示和保存结果另做完整核对。非空STRING实测使用含双引号的PLC字面，JSON写成`"initial_value":"\"Bridge text\""`；双引号属于原生内容，工具不自动添加/删除引号。语法、容量及业务引用由调用AI和AutoShop处理，不新增业务正确性证明。

FB编辑器清单示例；REAL、STRING均支持四类别，INOUT仍为null：

```json
{"schema":1,"operations":[
  {"op":"add","name":"rLocal","category":"VAR","data_type":"REAL","initial_value":"1.250000","comment":"Real local"},
  {"op":"add","name":"sInput","category":"IN","data_type":"STRING<20>","initial_value":"\"Bridge text\"","comment":"Text input"},
  {"op":"add","name":"sOutput","category":"OUT","data_type":"STRING","initial_value":"","comment":"Text output"},
  {"op":"add","name":"rReference","category":"INOUT","data_type":"REAL","initial_value":null,"comment":"Real reference"},
  {"op":"add","name":"sReference","category":"INOUT","data_type":"STRING<20>","initial_value":null,"comment":"Text reference"}
]}
```

FC编辑器也用schema/operations，所有类别都不指定独立初值：

```json
{"schema":1,"operations":[
  {"op":"add","name":"rLocal","category":"VAR","data_type":"REAL","initial_value":null,"comment":"Real local"},
  {"op":"add","name":"sInput","category":"IN","data_type":"STRING<20>","initial_value":null,"comment":"Text input"},
  {"op":"add","name":"rOutput","category":"OUT","data_type":"REAL","initial_value":null,"comment":"Real output"},
  {"op":"add","name":"sReference","category":"INOUT","data_type":"STRING","initial_value":null,"comment":"Text reference"}
]}
```

结构/GVT仍先table-export，再编辑changes.json。结构示例：

```json
{"schema":1,"operations":[
  {"op":"add","name":"rValue","data_type":"REAL","comment":"Real member"},
  {"op":"add","name":"sLabel","data_type":"STRING<20>","comment":"Text member"}
]}
```

GVT示例：

```json
{"schema":1,"operations":[
  {"op":"add","name":"grValue","data_type":"REAL","initial_value":"1.250000","comment":"Global real"},
  {"op":"add","name":"gsLabel","data_type":"STRING<20>","initial_value":"\"Global text\"","comment":"Global text"}
]}
```

已有BOOL/INT/DINT和结构引用流程保持原profile；含REAL/STRING成员的扁平结构变量及FB接口按本页s24首节处理，不能由直接标量新增推定ARRAY、嵌套或任意复杂初值也已支持。两种模式都保留身份、未保存状态、基线、唯一备份、完整正文/整表回读及非目标保护，正文和多文件修改由调用AI组织。

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
最后更新：2026-10-31

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

- FB：已有注释及支持标量初值set；BOOL/INT/DINT及s23 REAL/STRING直接声明保持原行为。VAR/IN/OUT标量初值为字符串，INOUT标量必须null；IN/OUT/INOUT可新增项目结构，内部VAR可新增项目结构或项目FB实例，复杂类型initial_value必须显式null，交给IDE默认初始化。含REAL/STRING成员的扁平结构及注释profile见本页首节。宿主须为已支持LiteST FB，不能用此入口直接修改LD宿主。
- s20方法二可引用准确登记的LiteST/已识别LD项目FB，以及真实类型选择器中的点限定库类型，例如`TRIG.R_TRIG`。冻结准确根定义身份及可读定义文件哈希，不递归证明成员、引用或业务类型使用正确。真实选择器须准确唯一命中；方法二未登记单段库名及未知原生布局仍未实现。方法一库/LD的s21用法见上节，不向editor-variables清单加入type_kind。
- 内部VAR选择器未读取类型分类，未登记点限定名称先标`ide_resolved`，不预断为FB。保存后只接受原生64（结构）或256（FB），核对实际名称/类型文本、VAR类别和已知默认字段；结果`named_type_resolution`与备份`native_added_variables.json`记录实际类型及初值。未保存状态仍待原生回读，不能据此报告已确认FB类型。
- 空表或仅有复杂声明的非空表，可在备份后创建并核对准确默认行，再延后类型选择器预检；有可用标量行时先预检。dry-run不创建行。失败可能留下已知未保存行，先回读现场，不盲目重放。
- FC：独立六列表，没有初值/保持列；已有注释set，VAR/IN/OUT/INOUT标量新增initial_value必须null，s23 REAL/STRING见直接声明一节。s11支持空表首项：备份后核对默认VAR/BOOL六列行，再预检类型/类别选择器。失败可能留已知未保存首行，停止、回读，不保存或重放。dry-run不创建行，selector_preflight=pending_first_default_row表示仍待真实预检。数组/结构等复杂类型、返回类型、FCI和新建FC仍未实现。不要把FB示例字符串初值套给FC。
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

上述s22路径已在同一既有empty02副本完成正式FC声明、FC文件候选及FBI追加、完整回读，组合和恢复均0错误并发布；它不是s23新增类型的验收结论。HCP被IDE锁住而需窗口声明编辑时，另按[项目登记基线](project-registration.md)显式绑定；offline文件写入仍先关闭工程并使用自己的直接HCP基线。

## 结构/GVT双模式

### s30普通根引用请求示例

以下名称为自造示例，`RegisteredRecord`须替换为调用工程准确登记且非空的结构根名。只编辑独立changes清单，不修改只读快照或原生文件。

STRU成员清单（无初值字段）：

```json
{"schema":1,"operations":[{"op":"add","name":"nestedItem","data_type":"RegisteredRecord","comment":""}]}
```

GVT结构根声明清单：

```json
{"schema":1,"operations":[{"op":"add","name":"recordItem","data_type":"RegisteredRecord","initial_value":null,"comment":""}]}
```

文件模式的命名结构新增使用闭工程`offline-export/check/build/apply`工程上下文；将相应操作放入准确目标的`variable_operations`，按[离线开发](offline-editing.md)的targets格式组织。独立旧`table-check/build/apply`没有取得新增工程类型目录资格。编辑器模式沿`table-editor-edit`，绑定当前准确工程／表／PID及冻结基线，显式保存后完整核对。不要在文件修改后保存旧窗口；保存后先刷新登记凭据再开始另一轮保存。

文件模式保持已有同名CSV全部原字节。非空表正常IDE保存的已验伴随变化限定为完整旧prefix保持、缺失root按名称追加四个空槽；本批空表0→2保存另有独立reset profile：保留同UTF16LE BOM及三行header，原16组20行四槽均为空，输出仅当前两根四空槽（1222→290字节），并核原native空表及新native整文件候选exact。槽位语义、reset原因及显示id含义未推断，不增加通用reset权限，不称永久无关缓存，不由工具补造CSV或放宽未知差量。任何未知伴随变化停止并保留实际保存、原始错误及备份，不能重发新增凑通过。

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

结构成员add只有op/name/data_type/comment；GVT新增标量还需initial_value字符串。BOOL/INT/DINT保持原规则，BOOL用ON/OFF，INT/DINT用规范十进制；s23 REAL/STRING见直接声明一节。结构定义没有初值/保持/地址。方法二的空/非空GVT支持准确登记的非空结构根；本候选增加含ARRAY／嵌套成员根的普通引用，初值必须null，不递归生成成员值。s24扁平REAL/STRING历史范围与s30限定原生验收／待验软件包状态分别见首节；方法一结构引用新增走offline系列，旧table-check/build/apply不新增结构类型变量。已有结构成员名称走正规改名；类型/保持/地址和删除不在此普通add/set接口中。

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
