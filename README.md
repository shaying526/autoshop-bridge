# AutoShop Bridge

让 AI 读取和编辑汇川 AutoShop 工程。

- 查看程序、变量、结构体和 FB 实例，支持只读检查梯形图。
- 工程保存并关闭后，通过 CLI 批量编辑已支持的原生文件。
- 工程打开时，通过 Windows 编辑器模式读取缓冲区并按需保存。

## 快速开始

1. 下载并解压完整目录，将包含 `SKILL.md` 的 `autoshop-bridge` 目录放入客户端的 Skill 目录。具体路径见[安装说明](references/environment.md)。
2. 在 Codex 中使用 `$autoshop-bridge`，提供 AutoShop 工程路径和要处理的对象。

也可直接使用 CLI。将 `$skill` 设为 Skill 目录，`$project` 设为工程路径。

```powershell
python -B "$skill/scripts/check_bundle.py"
python -B "$skill/backend/autoshop_bridge_cli.py" scan "$project"
```

需要 Python 3.9 或更新版本。编辑器模式还需要 Windows、PowerShell 和已打开的 AutoShop 工程。

[离线编辑](references/offline-editing.md) · [数据编辑](references/data-editing.md) · [能力范围](references/capabilities.md)

## English

AutoShop Bridge lets AI assistants read and edit supported Inovance AutoShop projects. Install the complete Skill directory, then provide the project path and the object you want to work with. See the [setup guide](references/environment.md) and [offline workflow](references/offline-editing.md).

[MIT License](LICENSE)
