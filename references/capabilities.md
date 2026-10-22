# 能力和证据边界

整理方式：AI 根据后台1.02代码、公共契约1.2.0/r12及既有验收报告整理  
当前状态：精简分发说明；后台历史现场证据与本包验证分开  
最后更新：2026-10-23

所有公共能力仍由原CLI或`autoshop_bridge.service.__all__`提供，没有新增MCP/业务API。CLI的`命令 --help`是参数事实来源；下表是可用范围，不表示每种类型组合都在AutoShop实测。

| 任务 / 入口 | 输入与输出 | 副作用 / 依赖 | 实现及验证 |
| --- | --- | --- | --- |
| 工程摘要/扫描：project-summary、scan | 绝对工程目录或唯一HCP；有界摘要或完整JSON文件 | 读取磁盘/登记镜像，可能标记possibly_stale；不反映未保存缓冲 | 已实现，既有工程只读验收；完整编译器语义未实现 |
| 检索：code-context、code-query | 符号、关系、limit/offset；定义/引用/调用/直接影响候选 | 磁盘只读；coverage=partial，词法候选非确定调用图 | 已实现，样本与自动检查；传递影响/完整作用域未实现 |
| 正文：export、source-read/patch/restore | 原生ST/FB/FC→工作目录source.st；唯一原文补丁/哈希→差异、片段、备份 | 导出/补丁写外部工件；variables.json只读 | 已实现；限定正文及增删行有原后台用户编译证据 |
| 文件直改模式：check/build/apply、backup/restore | 工作目录/原生基线；候选、替换结果、唯一备份 | apply/restore写原生；覆盖前校验和备份；非工程事务 | 已实现；ST/FB/FC正文同LF及限定表操作有历史验收，未知元数据不生成 |
| 正文编辑器：editor-open/read/sync/save/close | 工程、准确程序名、可选PID、工作目录/快照；缓冲/保存/回读状态 | Windows/已打开工程；可自动打开标签，sync默认不保存 | 已实现；ST/FB/FC正文限定场景保存及人工编译已验，其他版本/桌面未验 |
| FB/FC变量：editor-variables | schema=1操作清单、原生哈希；整表和保存结果 | 改缓冲，显式保存；复杂类型/依赖和整表保护 | 已实现限定范围，见[变量操作](data-editing.md)；并非所有组合现场验收 |
| 结构/GVT：table-export/check/build/apply、table-editor-read/edit/close | 独立table工作目录/changes.json；成员/声明、候选、备份、保存结果 | 文件及编辑器两模式；GVT新增核对全部同目录GVT | 限定字段及BOOL/INT/DINT普通新增两模式历史编译通过；DINT既有初值修改/极值只有自动测试 |
| 全局FB实例：instances-editor-read/add | 准确表名、清单、FBI哈希；整表、备份和软件分配地址 | 仅非空已识别实例表，新增已解析项目FB；保存不等于编译分配完成 | 已实现；定时器内部/全局实例有历史验收；库实例、删除、通用文件写入/恢复未实现 |
| 系统定义：system-variables-read | 工程+用户本机安装definitions-dir；表/类型/search有界结果及来源哈希 | 只读厂商XML，随包不带XML，不是PLC实时值 | 已实现；单型号、部分表与窗口核对，其余型号/地址单位未验；SVT不是空GVT |
| 编译反馈：build-baseline/report | 本轮基线与用户取得的真实日志；reported_pass/fail/未解析诊断 | 仅写报告；compile_freshness=unverified | 已实现文本解析，真实故意错误/修复有历史人工反馈；自动编译、面板读取未实现 |
| 多对象：change-check/run | source/table步骤及依赖计划；逐步日志、失败及未执行清单 | 同一组同一种模式；editor步骤保存；无原子性/自动回滚 | 已实现；两步历史保存/编译通过，中断恢复仅自动检查；变量新增不在组内 |
| 新建：object-dialog/create-st | 人工已打开正常对话框、dialog哈希、名称/初始源码；实际名称/登记状态 | 创建并保存LiteST，软件可能加SBR_；失败可能已建对象 | 已实现受限入口；分步创建历史通过，完整新CLI另建对象尚未现场重跑；FB/FC/表创建未实现 |

原后台现场基准：Windows10、AutoShop V4.11.0.5、Python3.9.1；308项回归是V1.02历史自动结果。Python3.12仅更早阶段离线检查，不是当前新增能力或真实IDE已验。分发包的实际本轮结果见[验收说明](validation.md)，不能继承为本包已做真实编译。

梯形图只返回`language=LD`/`ladder_not_supported`，不读取或改写其逻辑；硬件、轴/总线配置、PLC下载/启停/强制IO、MCP、安装器、异步进度/取消、稳定业务错误码及自动编译均不在本次交付。
