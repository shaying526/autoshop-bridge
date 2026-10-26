# 环境、执行和故障处理

整理方式：AI 根据现有运行实现整理  
当前状态：固定后台1.03的部署与调用约束  
最后更新：2026-10-23

## 环境和路径

Python3.9+，仅标准库，无pip安装步骤。用`python -B`加绝对CLI路径；不依赖cwd，不改PYTHONPATH或系统配置。JSON输入UTF8无BOM，源码UTF8无BOM，保留合法LF/CRLF，不使用孤立CR。JSON输出可能转义中文，解码后阅读。`--version`为文本，其余业务命令为JSON。

方法二需Windows同一交互桌面、Windows PowerShell/.NET Framework Accessibility和已打开的AutoShop工程；不是官方SDK。按工程完整目录及可选`--pid`定位，不按前台窗口猜。命令可自动打开/切换目标标签，不自动打开/关闭工程，不自动处理模态提示。不需要自行启动桥接服务、常驻进程或MCP。目标未打开时报告用户打开准确工程后再做只读探测。

完整包携带固定C#/PowerShell源码，不带AutoShop、厂商XML或编译缓存。未部署预编译grid Host时，工具按原逻辑运行系统PowerShell并编译固定C#辅助代码；调用者不编写或重新设计C#。后台维护者可另行部署经过验证的Host，新电脑仍须验证。现有超时是分步骤的，不是完整调用总时限；整表可能数秒至十几秒，写入可能数十秒。无公开进度/取消回调，不启动第二次写操作来“补救”等待。

Skill安装目录只读使用。工作目录、普通源码、操作JSON、结果和日志放用户指定的独立外部工件目录。备份默认在原生目标旁`.autoshop_bridge_backups`，可用命令真实支持的`--backup-root`指定外部位置；备份是不可覆盖新目录，不能当缓存清理。锁文件由工具维护，不自行删除。

## 安装完整性失败

检查器验证清单中的文件字节及**完整文件集合**。Git仓库工作目录和可直接运行的Skill安装目录是不同用途：不要把带`.git/`的克隆目录直接作为安装目录；从可信发行包或仓库干净导出取得完整内容，放到全新安装目录。不要在包内保存测试输出、额外说明或`__pycache__`，按入口使用`python -B`。

`bundle_invalid`时先停止所有工程操作。版本或帮助能运行不等于包有效。多余文件错误会列出`unexpected_count`及最多10个相对路径（每项最多200字符）；缺失或内容不匹配也会报告相应资源。保存错误摘要，保留当前安装不动；不要删除未知文件、重写清单或跳过检查。取得可信完整包后部署到**另一个新目录**，重新检查通过才继续原任务；没有完整包或部署授权时向用户报告阻塞。清单校验不是签名，不能证明下载来源可信。

## Python可选入口

以本次Skill位置定位`backend`并插入**当前进程**搜索路径，只调用公共service函数、使用关键字和绝对Path。不要导入内部格式/窗口适配或测试backend。完整参数仍查CLI帮助或后台公共契约，不凭本例猜其他函数参数。

```python
from pathlib import Path
import sys
sys.dont_write_bytecode = True
backend = (skill_dir / 'backend').resolve(strict=True)
sys.path.insert(0, str(backend))
from autoshop_bridge import service
assert Path(service.__file__).resolve().parent == backend / 'autoshop_bridge'
result = service.project_summary(project=project_dir.resolve(strict=True), limit=20)
```

`skill_dir`和`project_dir`由任务提供的绝对Path，不能用cwd或示例路径代替。调用同步阻塞；同一会话/工程串行，不共享并发窗口适配器，无进程级统一调度/整体事务承诺。环境缺失时不安装全局依赖或修改后台。

## 状态、失败和恢复

工程读取先尝试HCP；Windows权限失败后以普通只读句柄、READ|WRITE|DELETE分享重试，仍遵守已有句柄限制；仅WinError32明确标记sharing_violation。仍不可读时，只读摘要/扫描/查询可从同名HCPP作有界登记提取：验证支持的头部、压缩长度/CRC32、解压上限/完整流、全部成员边界、路径和重复，再要求剩余恰好四字节。尾字段的业务语义尚未知，返回mirror_validation及原值，不能把CRC通过视为完整格式已支持。registration_source.possibly_stale=true必须保留；磁盘正文/变量不取镜像源码，未保存缓冲不在磁盘结果中。普通内部登记、类型依赖和创建仍保持严格；s7另提供[闭时登记凭据](offline-editing.md#hcp占用时的目标正文凭据)，只在直接HCP快照、同一进程当前工程树、全部依赖与目标正文均匹配时供editor-read/sync使用。有界HCPP未知头尾只保留证据，不默认证明登记新鲜。保存或对象/依赖变化后旧凭据失效。HCP共享限制本身没有解除，只读摘要成功也不保证其他编辑器入口可用。

HCPP缺失、损坏、未知头部/边界或不匹配登记会同时报告HCP/HCPP原因。核对磁盘与窗口差异，保存需要保留的修改后关闭整个目标工程再重试；只关标签不足，无需退出整个AutoShop，不自动保存旧窗口。已知绝对路径的单文件export不依赖工程登记。

摘要/扫描成功不等于所有对象可解析；检查逐项status/error及覆盖范围，配置、空表/实例的未支持布局和缺失文件不能说成全部正常。工程登记无法读取时，用户已明确的单文件绝对路径仍可独立export只读，不能把结果当作完整工程清单或据此扩展写入权限。

CLI错误通常stderr输出`{"status":"error","error":"..."}`、退出1；`blocked`也退出1。Python常见BridgeError/ConflictError，部分文件错误可为OSError。旧接口没有统一稳定业务错误码；offline和registration实验入口分别返回已文档化error_code，不能据此绕过保护。退出0只表示命令相应阶段完成；尤其创建pending、部分修改日志、reported_pass等仍需检查具体语义。

冲突/未知布局/哈希不匹配/旧补丁/备份失败均停止依赖写入。失败可能已改部分缓冲或建了对象，保护错误和备份路径，读取实际正文/整表/磁盘，核对已做/未做，再讨论后续；不盲重试、自动保存或自动回滚。无条件复制备份覆盖工程登记/FBI不受支持。

`source-restore`仅恢复外部工作目录普通源码；原生`restore`保护恢复前状态但不刷新IDE。offline批次恢复必须传apply返回的receipt外部摘要，且当前全部基线仍匹配；失败可能partial，没有整体事务或自动回滚。已验FB/FC/结构/GVT文件写后重开标签不足，需重开工程；加载新文件前不要保存旧窗口。ST已验标签重开刷新，不能把此行为推广到全部类型。旧会话编译通过不是新文件加载证据。

成功验收至少对应任务要求：候选完整解析/回读、实际写入哈希、备份可定位、目标之外原生内容保持；编辑器保存还要全文/整表与磁盘回读。编译需要用户明确反馈本轮结果，设备运行需另验。报错只返回必要摘要，不回传整个客户工程。
