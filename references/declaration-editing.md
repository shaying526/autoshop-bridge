# 明确删除已有声明

适用s14 / CLI 1.03。仅使用当前包的命令和本次读取的哈希，不向旧editor-variables或table-editor-edit清单塞入delete。

删除不检查引用、调用或类型使用者，不自动级联修改正文或其他定义；模型/用户安排引用处理，AutoShop编译检查语义。目标身份、格式边界、旧记录/文件哈希、外部修改、唯一备份及完整回读仍必须通过。编辑成功不等于编译通过。

## 支持范围

| 目标 | 文件直改模式 | 编辑器操作模式 | 删除最后一项 |
| --- | --- | --- | --- |
| 已识别ST/LiteST FB变量 | offline系列 | editor-declarations-delete --kind fb | 支持 |
| 已识别ST FC变量 | offline系列；不接受source_file | editor-declarations-delete --kind fc | 支持 |
| 结构成员 | offline系列 | editor-declarations-delete --kind stru | V4.11.0.5菜单禁用，至少留一项 |
| GVT声明 | offline系列 | editor-declarations-delete --kind gvt | 已观察严格空表profile支持 |
| FBI全局实例 | offline系列；只删除已有记录 | editor-declarations-delete --kind fbi | 完整已观察empty_table profile支持 |

梯形图FB变量不是本入口的目标格式。其他文件为LD/FBI/SVT不会因引用覆盖不明而阻断已识别目标。FBI只移除计数及完整目标记录，幸存记录、地址及不透明前后容器原字节保持；不构造新实例、重分配地址或忽略未知布局。空FBI首项/第二项由instances-editor-add实现，见[实例操作](data-editing.md#全局fb实例)；不提供通用离线新增。

## 取得当前基线

变量沿用SKILL.md：skill安装目录、目标工程及输出目录相互独立。以下Block及probeLocal都是合成名称，实际路径由本次扫描或用户明确提供。

```powershell
python -B $bridge declarations-read "$project/Block.FB" --output "$artifacts/declarations-before.json"
```

支持.FB/.FC/.stru/.gvt/.fbi。结果文件含status=read、read_only=true、kind、declcount、native_sha256、declarations及authorizes_write=false。每项有name、record_sha256及已取得的类别/类型/注释/初值基本定义，不带ST正文。指定output时stdout仅摘要；不指定时stdout返回完整JSON。输出文件必须全新。

制作独立changes.json（1–32项），名称必须准确，expected_record_sha256取该项本次实际record_sha256：

```json
{"schema":1,"operations":[
  {"op":"delete","name":"probeLocal","expected_record_sha256":"<本次记录哈希>"}
]}
```

示例中的哈希须替换为真实结果，不能猜测。读取不构成写入授权。当前delete不与add/set混用；需要组合时分阶段、完整回读后更新基线。

## 编辑器操作模式

目标工程必须已打开且身份/PID明确。命令可通过--open打开目标标签，不会打开或关闭整个工程。

```powershell
python -B $bridge editor-declarations-delete --project $project --object Block --kind fb --changes "$artifacts/delete.json" --expect-sha256 $nativeHash --pid $pidValue --dry-run
python -B $bridge editor-declarations-delete --project $project --object Block --kind fb --changes "$artifacts/delete.json" --expect-sha256 $nativeHash --pid $pidValue --open --save --experimental --backup-root "$artifacts/backups"
```

$nativeHash取native_sha256，$pidValue是目标本次PID。dry-run只核对已打开标签，不开标签、不删除、不保存；若尚未打开，先按授权editor-open或对应表读取命令打开。真实执行需experimental；省略save只改缓冲。命令使用已观察的正常整行删除菜单，核对全部幸存行、正文及非目标文件；保存要求完整原生匹配。FB仅允许单独已观察的全零未知字段行表刷新。

- declaration_delete_ready：预检通过，未执行删除。
- declarations_updated_not_saved：仅缓冲修改，requires_manual_save=true。
- declarations_saved_verified：已保存且完整回读通过；declaration_count为结果数量，sha256为保存后原生哈希，native_validation为exact或限定FB行表归一化。
- reference_check=not_performed_by_design：按设计未查引用，不是遗漏；autoshop_compile_verified=false表示未编译。

备份路径backup中有原件、操作前整表、预期结果和阶段日志。失败抛错可能已有部分缓冲修改或已经保存；日志保留stage、completed_operations、save_requested及错误。不盲目重放、不保存未知缓冲、不假定自动回滚。单次辅助超时不等于整个操作时限；没有公开进度或取消。

## 文件直改模式

先保存需要保留的修改并关闭整个工程，随后按[离线开发](offline-editing.md)export/check/build/apply/restore。关闭单个FB标签不足以重载。将操作放在目标的variable_operations中：

```json
{"schema":1,"targets":[
  {"file":"Block.FB","variable_operations":[
    {"op":"delete","name":"probeLocal","expected_record_sha256":"<本次记录哈希>"}
  ]}
]}
```

file为准确登记相对路径。FB可显式另给source_file修正文，这不是自动引用清理；FC删除不接受source_file。冻结直接HCP/全部基线，使用外部plan摘要，首写前完成全部唯一备份，写后完整回读并保护非目标文件。applied仅磁盘成功，需用户重开工程，再回读和编译。多文件无整体事务/自动回滚。

恢复文件批次优先使用其offline-restore receipt及外部摘要。单原件backup/restore也支持已识别FBI，要求原件/当前profile可解析、源目标扩展匹配、当前哈希和恢复前新备份。文件恢复同样先关闭工程，之后重开，不能在旧窗口上保存回去。

## 验证边界

后台已在Windows10 / AutoShop V4.11.0.5 / Python3.9.1独立副本验证：两模式明确删除、FB/FC/GVT/FBI严格profile删空及备份恢复；保留引用可导致预期编译错误，恢复后全部编译0错误。窗口GVT展开监视与声明缓存重叠的读取已修复并实测，不以磁盘值冒充窗口值。包本身的合成冒烟不是AutoShop验收，更不是设备运行验证；空FBI正式首项/第二项保存、重开和完整回读已验；删空保留调用时3错误，恢复71项后全部编译0错误。新机器/版本、新空白工程严格登记及未知profile另验。
