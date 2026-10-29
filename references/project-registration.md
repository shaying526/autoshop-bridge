# 显式项目登记基线

s22开发限定验收已通过，第三项追加、恢复及原生最终审计均通过；本页随s22完整包提供，完整交付另做校验。仅在实际安装已支持下列命令后使用；不要修改包清单或旧凭据取得此能力。

## 何时使用

工程打开时HCP可能被IDE独占；未知HCPP头尾只能有界读取，不能证明镜像登记实时。普通无参数路径继续严格处理，不接受未知字段取得写资格。需要在这种工程中扫描、编辑声明或正常新建对象时，显式捕获关闭后的直接HCP项目基线，重开后由工具核对同一进程/工程、完整已映射对象树和全部冻结文件。

该基线是独立协议，不扩大旧`registration-capture`/`--registration-receipt`的已有目标正文范围；两种凭据不能混用。基线、输出及备份放在工程和Skill安装目录之外，使用新的绝对路径。

## 捕获与调用

先按用户意图保存需要保留的内容并**正常关闭整个目标工程**，保留同一AutoShop空白进程；关闭标签不足够。下面的捕获只读取，不自动保存、关闭、重开或编译：

```powershell
python -B $bridge project-registration-capture --project $project --pid $pidValue --output "$artifacts/project-registration.json"
```

必须使用本次确认的PID，不能照抄历史窗口身份。结果应为`project_registration_baseline_captured`；其中`mutation_authorized=false`表示捕获本身不授权工程写入。工具冻结直接HCP原字节、登记行、完整已映射对象身份、所有登记文件的存在/缺失及哈希和额外原生集合，不使用HCPP签发基线。

目标工程在同一进程/启动身份/主窗口正常重开且干净后，给本次命令显式传基线：

```powershell
python -B $bridge scan $project --project-registration-baseline "$artifacts/project-registration.json" --output "$artifacts/scan.json"
python -B $bridge editor-read --project $project --program $program --pid $pidValue --open --project-registration-baseline "$artifacts/project-registration.json" --output "$artifacts/program-before.json"
python -B $bridge editor-variables --project $project --program $program --pid $pidValue --changes "$artifacts/variables-changes.json" --expect-sha256 $nativeHash --project-registration-baseline "$artifacts/project-registration.json" --experimental --save
```

变量清单仍按[变量和表](data-editing.md)组织，哈希取本次真实读取；基线不是替代正文/整表、未保存状态、并发、备份和写后回读的通行证。每次命令进入、注册读取及成功返回前均检查相关状态；只有明确写目标及既有写入器已验证的关联变化可变化。无关文件、树身份或脏文档变化会停止。

`--project-registration-baseline`仅接入以下CLI：

- `scan`、`project-summary`、`code-context`、`editor-read`、`editor-sync`、`editor-variables`。
- `table-editor-read`、`table-editor-edit`。
- `instances-editor-read`、`instances-editor-add`、`instances-editor-edit`、`instances-editor-initial-read`。
- `object-plan`；`object-create`自动绑定已验证plan内的基线，不另加这个参数。

正文工作目录先按[source-editing](source-editing.md)准备和预检，再给`editor-sync`同一项目基线；其原native哈希/正文/保存保护保持，旧正文凭据不混用。不要给旧`build/apply`或`offline-*`添加此参数。已有正文凭据仍沿其独立接口；关闭工程的offline流程直接读取HCP，仍使用自己的完整工作目录基线。

## 正常创建与持久登记待确认

正常创建LiteST FB或结构时，将基线给`object-plan`，其余名称、初始正文/成员和保存选项依实际需求提供：

```powershell
python -B $bridge object-plan --project $project --pid $pidValue --kind litest-fb --name $newName --source-file "$artifacts/initial.st" --output "$artifacts/object-plan.json" --project-registration-baseline "$artifacts/project-registration.json" --save-project
python -B $bridge object-create --plan-file "$artifacts/object-plan.json" --experimental --backup-root "$artifacts/creation-backups"
```

`--save-project`是本次明确保存工程登记的选项，不授权自动关闭工程。创建只允许计划内一个新对象/文件，原有对象及非目标保持；工具核对正常创建对话框及实际新目标，软件生成容器和登记，不手写HCP或猜新对象ID。

来源`kind=closed_hcp_live_tree_verified`及`registration_mapping_scope=captured_objects_only`只说明关闭时捕获的映射已按本次实时树/文件核对。HCP仍被锁住时，`current_hcp_verified=false`；新增对象不能被旧捕获映射冒充为已持久登记。

创建成功保存正文/成员后仍可能返回`object_created_pending_registration`及`requires_project_registration_refresh=true`。若`--save-project`已经执行，结果会说明仍需`close_and_capture_direct_hcp; do_not_repeat_creation_or_save`：按授权正常关闭工程，重新直接捕获HCP，核对旧登记保持和唯一计划新增，再重开使用新基线。不要循环保存或重新创建来消除pending。

## 失效与异常

保存后原生文件、依赖、对象树、工程或进程身份变化都会使旧文件基线失效；下一次修改先正常关闭并重新捕获。可以在一个受支持的清单中组织多项修改以减少重复生命周期操作，但不能篡改凭据哈希续用旧基线。未保存缓冲先按现场处理，不靠关闭丢弃或伪造干净状态。

非0、未知模态或写入结果不确定时停止依赖写入。错误若带`operation_result`和`operation_may_have_completed=true`，表示写入可能已经完成而最终保护停止；先完整核对当前状态及备份，不重放。工具不自动重试关开、保存、编译或恢复，不操作PLC；Skill也不新增这些授权。

## 本轮实际范围

同一既有empty02安全副本未手改未知头尾：正式scan、FC声明编辑、FB初始化及结构完整创建已验证；FB首次异步标签守卫停止后按现场恢复，没有重发创建。关闭直读HCP确认旧46登记行及唯一新增结构。空FBI两项已保存、重开完整回读，2026-10-29 21:03:55组合编译0错误；第三项终态写入已完成，21:11:23组合及21:16:23恢复均0错误；14根原生与起点字节相同并干净关闭。该证据不等于未知HCPP已被完整解析，也不扩大到任意版本、未知容器或自动工程生命周期。

`editor-sync`可用同一项目基线接入既有正文工作流（CLI路由/别名有回归，本批未另重复其真实正文保存验收）；初始空白ST等未识别原生容器仍单独未实现，不以登记资格冒充格式支持。未知HCPP并未解码，最终软件保存/编译可正常改变头尾；工具不清零、改未知字段或要求变零。
