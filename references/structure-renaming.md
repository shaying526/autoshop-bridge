# Existing structure member names

结构成员正规改名支持单项及批量，保持成员顺序、类型、注释和其他属性。AI负责正文引用及业务语义；本工具不要求先证明旧名已无引用，也不自动替换正文、注释中的同名文字或其他业务对象。

目前通过关闭整个工程后的文件工作流执行。工程级计划同时维护已解析ST FB中直接引用该结构的VAR/IN/OUT/INOUT初值成员键；只替换已观察完整成员注释模板中的键，原注释字节保持。s20新增混合空/非空注释模板，与平面结构变量新增共用序列化规则：只输出有注释成员，分隔符依据其在原定义中是否末项，末项无注释时保留尾随`, `。空注释成员改名不会凭空增加初始化键；完整旧串须匹配原定义，不解析或猜测值初始化。全空、全非空和`=`/`#`保持原行为。

空GVT/FBI初始化串保持；已知直接GVT结构初值按相同profile处理。未知非空嵌套FBI初值等尚未实现，不能伪造元数据。计划明确列出metadata_updates及未改写对象，不因无关LD或配置未解析阻断已支持目标。混合模板已完成正常IDE保存/方法一完整记录逐字节对照、正规rename关联键回读及组合/恢复0错误编译；各阶段仍分别记录。

## Batch plan and apply

使用本次准确的工程、独立新工作目录及工程外备份目录。先保存所需内容并关闭整个工程；工具不会丢弃用户未保存内容。下面名称为合成示例。

```json
{
  "schema": 1,
  "structures": [
    {
      "file": "InputData.stru",
      "renames": [
        {"old": "readRequest", "new": "sdoReadRequest"},
        {"old": "busy", "new": "sdoBusy"}
      ]
    }
  ]
}
```

```powershell
python -B $bridge structure-rename-plan --project $project --changes "$artifacts/renames.json" --workspace "$artifacts/rename-work"
python -B $bridge structure-rename-apply --plan-file $planFile --expect-plan-sha256 $planHash --backup-root "$artifacts/backups" --experimental
```

从首条JSON结果取得plan和plan_sha256作为$planFile/$planHash。它还列出每项旧名/新名、精确目标文件、自动更新的变量/字段。名称在整批最终结果中须可唯一识别；支持同时交换名称。plan不改工程；apply重新构建所有候选，成功状态applied只证明磁盘写入及完整回读，仍需重开工程读取并编译。

原始结构和关联文件、全部登记依赖在首写前唯一备份。receipt及receipt_sha256可用于既有offline-restore；恢复也需闭工程及新备份。partial表示可能已写部分文件，先检查receipt，不盲重放。旧计划、外部修改、备份失败、候选篡改会停止。

## Existing table commands

普通table-export工作目录的changes.json也接受名称字段：

```json
{"schema":1,"operations":[{"op":"set","name":"readRequest","field":"name","expected":"readRequest","value":"sdoReadRequest"}]}
```

table-check返回table_ready，并以execution=project_rename_batch及associated_metadata_pending说明关联检查在工程计划执行。table-apply会转入同一工程级改名工作流，结果为applied/partial/stopped及完整receipt；不会只写.stru后留下已知旧初始化键。此路径使用独立的name操作清单，其他字段另次正常编辑。多结构及同时交换建议直接使用structure-rename-plan/apply。

table-editor-edit尚未实现关联元数据同步；该新字段引导至上述文件模式。其他已交付编辑器能力继续使用原接口。支持范围与“禁止业务修改”不同：新增未支持的类型/字段应由后台实现，不能修改安装代码、清单或未知原生字节绕过。

## References and validation

references_updated=false、reference_check=not_performed_by_design表示正文引用留给调用者。完成改名后，通过[正文编辑](source-editing.md)修改已登记FB/ST正文；MAIN含未知行元数据时使用编辑器模式，不清零。然后重开完整回读，并单独记录AutoShop编译。编译错误不会撤销已成功改名，语法、变量声明和业务正确性由AI及编译处理。
