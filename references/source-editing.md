# 正文、补丁、保存与恢复

CLI 1.03补充：[关闭工程离线开发](offline-editing.md)处理已登记ST/FB增删行、FB空表首次标量/结构端口及GVT结构新增，必须采用独立offline工作目录/命令。下文旧正文或table入口的限制仍适用，不给旧build/apply添加不存在的参数，也不编辑只读variables.json。

整理方式：AI 根据现有CLI和正文工作流程整理  
当前状态：后台1.03的真实调用；示例名称为合成，不是默认目标  
最后更新：2026-10-23

## 输入与只读基线

沿用SKILL.md中由加载位置设置的`$bridge`，以及用户给定的`$project`、`$artifacts`；用新外部目录`$work`。先从摘要/scan取得准确原生路径`$native`和程序名`$program`，不猜扩展名、根目录布局或变量数。

```powershell
python -B $bridge export $native --workspace $work
python -B $bridge source-read $work --search 'Ready' --context 2 --limit 5
```

原生ST/FB/FC是二进制容器，不是明文源码，不能直接做文本替换或在原生字节中搜索明文来判断写入成功。`export`生成manifest.json、original.native、source.st；FB/FC另有variables.json。只可编辑source.st，其他文件均只读。`source-read`返回`source_sha256`和有界`rows`，不是直接读IDE；优先limit，不将固定end设到实际总行数以外。

正文为空不等于读取失败：受支持容器可导出0字节的source.st，source-read按LF数+1返回1个空行。零字节原生文件或未识别布局仍应报错；不要要求用户先填代码来掩盖解析问题。尚未识别的空工程登记或行表布局需要真实样本，不能由合成空正文测试推定全部兼容。

方法二在写前需要真实编辑器基线：

```powershell
python -B $bridge editor-read --project $project --program $program --open --output "$artifacts/before.json"
```

核对目标、`modified=false`、快照source编码后的字节与original.native导出正文相等、native_sha256与manifest一致。不同即停止，保护未保存内容/缓存差异；不能仅凭标签无星号继续。文件读取/编辑器写入不需要先apply。

## 本地补丁

创建UTF8无BOM的patch.json：schema=1，source_sha256取本次source-read，operations是1..100项顺序替换。每项只有old/new，old必须非空且在当步唯一；添加更多真实上下文解决歧义，不只凭行号。下面Python示例读取本次工作目录的真实字节生成一个**合成例子的**补丁，输入`work`/`patch_file`由外部绝对Path提供；只适用于确实存在该原文的示例，不照抄哈希到其他工程。

```python
import hashlib, json
raw = (work / 'source.st').read_bytes()
document = dict(schema=1, source_sha256=hashlib.sha256(raw).hexdigest(),
                operations=[dict(old='// Example original', new='// Example revised')])
with patch_file.open('x', encoding='utf-8') as stream:
    json.dump(document, stream, ensure_ascii=False)
```

```powershell
python -B $bridge source-patch $work --patch-file "$artifacts/patch.json" --dry-run
python -B $bridge source-patch $work --patch-file "$artifacts/patch.json"
```

补丁dry-run状态为`source_patch_ready`，实际更新为`source_patched`；不能把所有预检状态猜成ready。补丁仅改外部source.st，并在patch_history保护原文；不写原生/IDE。可直接编辑普通源码，但仍须保留合法UTF8和换行，不改任何基线清单。最多1000行（LF数+1，含空行）。

## 编辑器操作模式（方法二）：保留项目打开

```powershell
python -B $bridge check $work --method editor
python -B $bridge editor-sync $work --project $project --program $program --dry-run
python -B $bridge editor-sync $work --project $project --program $program --open --experimental
python -B $bridge editor-read --project $project --program $program --output "$artifacts/after-buffer.json"
```

每条先检查退出码/JSON再继续；editor-sync的dry-run检查实际会话，不能同时`--open`，因此先editor-read --open。默认返回`editor_updated_not_saved`：备份成功、缓冲回读通过、原生未改，仍需用户自行保存或明确后续保存。若任务已要求保存，在**首次实际同步**命令上加`--save`；`--close`须同时保存，只关闭目标标签。

先改缓冲、后收到保存要求时，使用最新完整editor-read快照：

```powershell
python -B $bridge editor-save "$artifacts/after-buffer.json"
```

快照必须仍匹配当前缓冲；不重跑旧editor-sync保存脏缓冲。保存后检查`editor_saved`、完整正文/变量和原生回读，再export到全新工作目录。不要复用保存前的旧manifest。FB/FC保存后行记录可能滞后，仍可读，文件直改模式修改另受严格保护。

## 文件直改模式（方法一）：关闭工程期间写原生

用户已确认目标工程关闭且选择离线写入后，使用同一export/补丁流程，但不调用editor命令。

```powershell
python -B $bridge check $work --method file
python -B $bridge build $work --output "$artifacts/program.candidate.ST" --experimental
python -B $bridge apply $work --experimental
```

候选扩展名应匹配真实原生类型；FC用.FC、FB用.FB。`build`输出必须不存在；它不改目标。`apply`备份成功后覆盖manifest绑定的原生目标，返回`replaced`/`backup`/`sha256`。同LF、行记录匹配及外部基线检查不可省。FB/FC重开工程加载后再人工编译，旧会话通过不算验收。

## 恢复、编译反馈及多对象

普通源码恢复：`source-restore WORK --saved PATCH_HISTORY_DIR --expect-sha256 CURRENT_SOURCE_HASH`，状态source_restored。原生恢复：`restore BACKUP_DIR --expect-sha256 CURRENT_NATIVE_HASH`，状态replaced；从结果取得真实备份路径/当前哈希，两种恢复都保护恢复前状态，不能混用source/native哈希。原生restore不刷新IDE，也不能通用于FBI/工程登记。

用户已准备本轮编译时：

```powershell
python -B $bridge build-baseline --project $project --output "$artifacts/build-baseline.json"
# 用户执行编译并提供真实文本后，才运行下一条。
python -B $bridge build-report --project $project --baseline-file "$artifacts/build-baseline.json" --log-file "$artifacts/compiler.txt" --encoding utf-8 --output "$artifacts/build-report.json"
```

`reported_pass/fail`仅是文本报告；compile_freshness=unverified、autoshop_compile_verified=false，不伪造日志，不自动编译/读面板。真实编译和PLC行为仍分别验收。

多对象需要已有source/table工作目录和schema=1计划：project为绝对工程目录，steps每项包含id/workspace/kind（source或table）/method（file或editor）/after（前置id列表）。`change-check --plan-file PLAN`先预检，`change-run --plan-file PLAN --journal NEW_DIR --experimental`按依赖执行。editor组会保存；同一组只能一种模式，FB变量/实例新增不属于步骤，无整体事务或自动回滚。失败查看日志实际阶段，不重放旧计划。
