---
name: autoshop-bridge
description: Read and modify AutoShop PLC projects using bundled scripts. Use for ST program bodies, ST-backed FB/FC, supported variables and structures, project queries, backups, editor synchronization and experimental read-only LD programs/FBs. Not for generic Python development, ladder editing, hardware configuration or PLC download/control.
---

# AutoShop Bridge

工具是工程编辑的执行层：AI负责语法、声明、引用和业务语义，AutoShop编译检查结果。正常创建、删除、修改不要求先证明业务正确，不额外增加人工审批；身份、未保存内容、并发、格式、唯一备份及完整回读用于保证执行准确。未实现字段应如实说明并走已实现路径，不能把旧白名单当永久禁止。

结构成员正规改名按[改名工作流](references/structure-renaming.md)：table-check支持field=name；table-apply或structure-rename-plan/apply同步已知关联初始化成员键。正文引用由调用者另行修改，旧引用不阻断改名。

FBI已有实例的名称、注释和初值走[既有实例编辑](references/data-editing.md#fbi已有实例编辑)：文件模式修改完整原生字符串；编辑器初值明确指定工具箱成员路径，先读取真实成员旧值。文件模式不改引用，正常IDE改名可能自动保存引用，按结果清单核对。

以随包固定版本的CLI处理用户指定的AutoShop工程。只调用工具；不要修改后台Python/C#、生成的清单或备份。Skill不增加授权，也不绕过宿主限制。

说明中的**文件直改模式（方法一，Direct File Mode）**对应程序标识`file`，直接读写磁盘原生文件；**编辑器操作模式（方法二，Editor Mode）**对应`editor`，操作AutoShop编辑器缓冲并显式保存。这里只统一说明名称，不改命令、参数、API或结果状态。

## 先取得输入并检查环境

明确工程绝对目录、目标对象/功能、验收条件、文件直改或编辑器操作模式，以及是否保存。遵守目标工程自己的规则；不默认选择最近打开的工程或自行复制客户工程。只读任务无需询问保存意图。

从**本次加载的SKILL.md绝对路径**取得其父目录作为`$skill`，不要使用当前工作目录猜测。下列变量由本次任务提供，全部使用绝对路径：

- `$skill`：本Skill安装目录。
- `$project`：目标AutoShop工程目录，和Skill安装目录无关。
- `$artifacts`：用户选定的独立输出目录，位于Skill和原生程序目录之外；每次工作目录/结果文件用新名称。

```powershell
$bridge = Join-Path $skill 'backend/autoshop_bridge_cli.py'
python -B "$skill/scripts/check_bundle.py"
python -B $bridge --version
python -B $bridge --help
python -B $bridge project-summary --project $project --limit 20
```

应读到CLI `1.03`、skill_revision `2026-10-28.s19`且包检查为`bundle_verified`；旧安装只看CLI版本不能证明已更新。`bundle_invalid`时停止工程调用，按[环境和限制](references/environment.md#安装完整性失败)定位部署问题。安装目录额外的`.git`或缓存也会被拒绝，不能删除未知文件或改清单绕过。Python要求3.9+标准库；方法二还需要Windows交互桌面、Windows PowerShell/.NET和已打开的目标AutoShop工程。不要自行启动服务、构建辅助程序或修改全局环境。

## 最短可靠流程

1. 先有界工程摘要；需要定义/引用时用`code-context`，按需导出和读片段，避免把整工程或窗口整表倾倒到上下文。已保存内容优先文件读取，磁盘不包含未保存缓冲。
   梯形图程序/FB读取改走[梯形图只读](references/ladder-reading.md)的随包独立脚本；已知文件绝对路径可直接读，不依赖HCP。先摘要，再分页读指定网络、引脚、连接和FB变量；不要用ST导出器或把默认scan的“仅识别”误当新读取入口。LD写入/排序仍未发布。
2. 选择模式。工程已关闭，需要正文增删行、空FB首变量、内部/全局项目FB实例或GVT结构变量时，读[离线开发](references/offline-editing.md)，使用独立offline系列，不沿用旧build/apply的同LF限制，也不能放宽未知行字段。方法二通过编辑器修改，可自动打开/切换目标标签；默认只改缓冲，显式`--save`才保存。不要先文件写入再用旧窗口/旧基线同步。
3. 正文任务按[正文编辑](references/source-editing.md)导出、核对基线、制作唯一原文补丁、预检并调用既有写入器。变量/表/实例新增修改改读[变量和表](references/data-editing.md)；明确删除改读[声明删除](references/declaration-editing.md)，使用独立declarations-read/editor-declarations-delete或offline入口，不向旧清单塞入delete。删除不查引用、不级联，语义交编译，完整性保护仍保留。不要把变量声明塞进正文或编辑只读快照。
4. 逐条检查退出码及JSON状态后再继续。备份成功、当前原文/哈希和完整回读不能省。保存后重新导出用于后续修改；同一工程/会话串行执行。
5. 分别报告缓冲更新、原生保存、回读、用户编译反馈和业务行为验证。只读或本地候选任务完成后，不额外写入/保存。

离线开发先export冻结直接HCP和依赖，再check/build，使用返回的plan摘要apply；所有备份先于首写，完整回读后由用户重开并编译。不要自动关闭用户工程。HCP占用而普通编辑器入口拒绝时，可按离线开发参考先由用户关闭工程，registration-capture后重开，再给editor-read/sync传--registration-receipt；这只允许已核对目标正文，不授权结构变更，不默认信任旧HCPP，保存后旧凭据失效。

常用只读调用：

```powershell
python -B $bridge code-context --project $project --symbol CalcDemo --max-items 20
python -B $bridge scan $project --output "$artifacts/scan.json"
python -B $bridge export "$project/CalcDemo.FC" --workspace "$artifacts/calc-work"
python -B $bridge source-read "$artifacts/calc-work" --start 1 --limit 20
```

以上`CalcDemo`及路径组成仅为合成示例；真实文件路径/名称从当次扫描取得，原生文件可能位于工程子目录，不能假定都直接放在工程根目录。先用limit安全读取；只有已知实际行数时才用end。`exported`只表示导出；`source_patch_ready`/`source_patched`分别是本地补丁预检/修改；`ready`/`editor_ready`是对应写入预检；`built`是候选；`replaced`是原生写入或恢复；`editor_updated_not_saved`是缓冲修改；`editor_saved`及`editor_saved_closed`是保存。编译文本`reported_pass`不是工具证实本轮编译。完整能力及验证范围见[能力边界](references/capabilities.md)。

## 必须停止的情况

- 退出非0、`blocked`、目标/PID歧义、未知格式/布局、未保存用户内容、磁盘与缓冲基线不同、备份失败、模态提示或结果不确定：停止依赖写入。先保存诊断摘要/备份路径、只读核对当前状态，再决定恢复或请求用户处理；不盲目重放写入、不保存旧窗口、不假定回滚。
- 旧文件入口发现行数变化或FB/FC行记录滞后，不能手补元数据；关闭工程后的ST/FB可按离线参考检查已实现profile，FC增删行仍用经授权的方法二。s15的offline系列支持已识别ST非零折叠缓存及增删行；未知值按具体行/字段/值报告，不清零绕过。混合成员注释等未实现范围另列。单程序上限1000行（LF数+1，含空行）。
- 默认scan仍仅识别`LD`；独立梯形图入口支持已观察格式的只读记录查询，未知布局拒绝。含内嵌ST禁止整图复制，先读磁盘正文，当前物化控件另读且不冒充完整实时混合图。系统变量只读；不编辑梯形图、不自动编译、不从编译面板取结果，不做PLC下载、启停或强制IO。更多未开放范围见能力表。

## 结果交付

说明目标与修改/只读范围、产物和不可覆盖备份位置、实际JSON状态、完整回读与非目标检查结果；明确哪些仅离线/模拟、哪些是用户本轮编译反馈、哪些未验证。错误只给必要对象/阶段和诊断，不输出整个工程或敏感内容。

需要部署验收或重放冒烟时，再读[两项目验收](references/validation.md)；普通读取/编辑任务无需加载验收文档。试用结果保存在包外开发记录，不作为新AI的操作答案。不能把合成容器当成AutoShop已编译工程。
