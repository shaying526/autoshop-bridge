# 梯形图只读 / Read-only ladder inspection

整理方式：AI 根据实际读取接口与已记录验证整理  
当前状态：s6 独立实验读取入口；不交付梯形图写入或排序  
最后更新：2026-10-25

Use the two absolute script paths below, separately from the existing ST CLI.
Prefer saved file reads. Editor reads require the already-open target tab and
Windows desktop, may change focus/selection and briefly use the clipboard.
They never paste, edit logic, save, compile or communicate with a PLC.

## 范围与输入

支持已观察格式的`.LD`梯形图程序、`.FB`梯形图功能块：网络标题/顺序、触点/线圈/边沿/支路线、已观察指令、FB调用的类型/实例名/引脚实参、连接成员、FB局部变量，以及磁盘中的内嵌ST正文。不是渲染器、仿真器、LD转ST工具或完整编译器语义解析。未知元件/布局明确报错，不猜成空逻辑。

用户给出目标工程与已确认的原生文件绝对路径；从本次加载的Skill位置定位`$skill`。`$native`不能用猜测的文件名，`.FB`不等于一定是LD，先确认语言。文件单独读取不依赖HCP/HCPP；它不保证工程清单完整，也看不到未保存缓冲。

```powershell
$ldfile = Join-Path $skill 'backend/tools/diagnostics/inspect_autoshop_ladder.py'
$ldeditor = Join-Path $skill 'backend/tools/diagnostics/inspect_autoshop_ladder_editor.py'
python -B $ldfile --help
python -B $ldeditor --help
```

不修改随包程序或manifest。不导入未随包提供的梯形图writer、排序、生命周期或编译调度模块。既有ST写入能力仍在原CLI中，本页的“只读”限定新增梯形图入口，并不声称整个Skill禁止写入。

## 文件读取（方法一，优先）

下面假定`$native`已是实际扫描得到的`.LD`或LD型`.FB`绝对路径：

```powershell
python -B $ldfile $native --section summary --limit 20
python -B $ldfile $native --section network --network 1 --offset 0 --limit 20
```

读取FB局部变量：

```powershell
python -B $ldfile $native --section variables --limit 20
```

`variables`仅对LD型FB有效；普通`.LD`结果的`variable_count=null`表示该容器没有提供变量表，不能解释为0项。普通程序的全局表仍走既有table接口。

`summary.items`列网络标题和记录数，`summary.network_marker_count`是实际文件标题记录数，包含空网络，不能只看界面最后一个编号。`network`返回分页图元及相关连接，FB调用在`block`中给出`name`、`instance_name`、有序`pins`（`name/actual/direction_code/descriptor_raw`）；方向0/1/2为已观察输入/输出/INOUT。`embedded_st.source`是该记录的已保存ST正文。

`next_offset`为下一页起点，null表示本列表结束；不要每次把全文件重新倾倒到上下文。连接可能引用本页以外的图元，必须取齐对应图元才分析支路。原始ID、mapping、调用尾字段和其他unknown按原值返回，不按数字推测执行语义。网络排序会改变执行顺序；本版不提供排序。

成功为退出0，`status=ladder_fb_inspected_experimental`或`ladder_program_inspected_experimental`，`read_only=true`，`logic_semantics_verified=false`。非0时查看stderr的`status/error`，不得改格式标记或跳过未知字段。输出仅stdout，无需AutoShop运行，不修改原生文件或生成缓存（保留`-B`）。

## 编辑器读取（方法二，可选）

需要本机Windows、AutoShop V4.11.0.5、正确工程及目标LD标签已打开。`$project`为绝对工程目录，`$program`为准确对象名，`$pid`来自当前会话身份；不默认选择另一个进程。此独立入口不能自动打开缺失标签，`--activate`只切换已打开标签。只读复制可以读取普通未保存图，但不保存它；不要把窗口结果称为磁盘结果。

先核窗口，不使用剪贴板：

```powershell
python -B $ldeditor --project $project --program $program --pid $pid --activate --section window
```

对**没有内嵌ST**的普通图，整图读取后分页查看网络：

```powershell
python -B $ldeditor --project $project --program $program --pid $pid --section diagram --limit 20
python -B $ldeditor --project $project --program $program --pid $pid --section diagram --network 1 --limit 20
```

`diagram`选择整图并复制，但不会粘贴或更改逻辑。默认只允许安全备份/恢复的空或文本剪贴板；未知OLE/图像在复制前停止，不能擅自清空。用户保留内容并明确同意临时覆盖后才可加`--scratch-clipboard`，此时不恢复原内容；安装Skill不是许可。`--preserve-supported-clipboard`是已观察文本/HTML/Chromium HGLOBAL白名单的显式恢复选项，不保证任意富文本安全，两选项不能同用。

结果为`status=ladder_editor_records_read_experimental`，`source=live_windows_clipboard`，`source_disk_read=false`，`complete_logic_read=false`。按`next_offset`取齐图元与连接，整图选择过程不证明所有版本/布局的完整逻辑覆盖；运行时连接ID可能重分配，不能仅按ID数值比较两模式。

读取变量表或**当前已经物化的**内嵌ST控件，不做整图复制：

```powershell
python -B $ldeditor --project $project --program $program --pid $pid --section variables --limit 20
python -B $ldeditor --project $project --program $program --pid $pid --section embedded-sources --limit 20
```

内嵌ST整图复制曾导致AutoShop异常，当前禁止重放；磁盘完整结构和内嵌ST优先用方法一读取。`embedded-sources`没有物化控件时返回0，只是当前可见/物化数量，不代表文件没有ST。它不将控件强绑定网络，也不提供完整实时混合图；不要以磁盘正文代替未读取到的窗口正文。

注意：编辑器`variables`是整表读取，现有实现不按`--limit`截断变量表；不要把该参数当作整表访问提速或内存保护。图元、网络及物化ST列表按各自分页语义返回。

如需落地完整编辑器JSON，可给复制命令显式`--output $newOutputDirectory`。必须是全新绝对目录，位于Skill安装目录及目标工程之外；生成`editor.json`，不输出剪贴板分配区剩余容量。变量与内嵌正文读取不接受该选项。退出非0、模态、身份歧义、剪贴板恢复失败或未知布局时，保留错误，先核对现状，不盲目重复。

## 验证与限制

既有真实证据：Windows10 / AutoShop V4.11.0.5 / Python3.9.1；普通LD程序、33变量的LD型FB、边沿/SET/RST探针及磁盘内嵌中文/空ST记录已与界面核对。读取不等于执行语义/编译/设备行为已验收。旧版Skill s5没有这些读取资源；s6本轮打包、重定位、真实只读复测状态见随包[验收说明](validation.md)，不据历史能力冒充新电脑验收。

当前仍不支持完整实时含ST整图、未知元件布局、梯形图写入/排序、自动打开缺失LD标签、梯形图自动编译/PLC操作。默认`scan`/公共service仍仅识别LD，须通过本页独立脚本读取，不把CLI1.02或“仅识别”的旧状态误当本页读取结果。
