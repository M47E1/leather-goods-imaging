# Leather Goods Imaging

**皮包商业图 Skill** — identity-preserving product-photo editing guidance, SKU-set consistency audits, modular prompts, and read-only image checks for leather goods and related bags.

面向背包、托特、肩包、钱包、卡夹及相关织物包的真实商品图。重点不是“生成更好看的另一个包”，而是修复已指明的问题、保留产品身份，并把可验证的结果交给采购/目录流程。

说明以中文为主，代码和CLI使用英文。可作为Codex Skill安装，也可独立阅读提示词与验收方法。本项目没有内置图像生成服务，不需要API密钥；只有可选的只读探针需要Python/Pillow。

## 包含什么

- **6个视图模块**：原机位、平视、轻俯、过侧回转、更平更远、仅调占幅。
- **25个局部模块**：去包装/细绳、铭牌、提手与背带、卡窗、拉片、褶皱、局部压缩、白底、缺边、去锯齿、反光、局部几何等。
- 参考图分角色、材料/五金保真、同款多视图与文字例外判断。
- SKU整套比较：主辅图包体占幅、颜色、机位与风格；不以1:1画布代替视觉一致性。
- 逐层几何检查：外框、内框、前袋、缝线、拉链、滚边/筋和圆角；正视直段按其真实设计查横平竖直，斜视保留合理透视。
- 第一性原理与对抗式审计：目标缺陷实际改善、材质与非目标部件不倒退；检查高清边缘、纯白背景及贴地阴影。
- 模块职责和冲突检查；需求路由、匿名案例、32个可人工核对的组合场景。
- 限次重试、只读审计、用户选版、上线核验与原片保留边界。
- 只读`image_probe.py`和20项合成/CLI测试，包括索引色调色板及透明度漏检回归。

入口：[SKILL.md](SKILL.md) · [SKU工作法](references/10-sku-commercial-workflow.md) · [第一性原理与对抗审计](references/11-first-principles-adversarial-audit.md) · [提示词模块](references/02-prompt-library.md) · [覆盖与场景](references/09-coverage-and-scenarios.md) · [匿名案例](references/07-lessons-and-cases.md)

## 安装与使用

将本仓库放在你的Codex Skill目录下，文件夹名为`leather-goods-imaging`。默认目录示例：

```powershell
# Windows PowerShell；目标已存在时不要覆盖其中的客户配置。
git clone https://github.com/M47E1/leather-goods-imaging.git "$env:USERPROFILE/.codex/skills/leather-goods-imaging"
```

```sh
# macOS/Linux 默认目录；自定义 CODEX_HOME 时使用自己的实际 skills 目录。
git clone https://github.com/M47E1/leather-goods-imaging.git "$HOME/.codex/skills/leather-goods-imaging"
```

任务示例：

```text
使用 $leather-goods-imaging。先只整理提示词，不生图。
这张指定候选只去背带上的白色包装纸，不改变机位和提手。
铭牌继续匿名，功能压印保留；请给出修改范围、不变量和验收条件。
```

实际工具可用性与执行授权由你的环境和当前任务决定。Skill不绕过图像工具的输入/查看要求，不自动生成、联网、发布、删除或安装依赖。

客户自己的尺寸、白底、命名、选图和例外写在私有项目配置中：[配置模板](references/06-project-profile-template.md)。未确认就不把某一客户的数值套到所有产品。

## 可选：只读图像探针

Python 3.10+；以下安装命令仅在你决定使用探针时运行：

```sh
python -m pip install -r requirements.txt
python scripts/image_probe.py /path/to/candidate.png
python scripts/image_probe.py /path/to/candidate.png --background-box 0,0,40,40
python scripts/image_probe.py /path/to/candidate.png --compare /path/to/source.png --protected-box 0,0,400,200
python -B -m unittest discover -s scripts -p "test_*.py" -v
```

背景框必须由使用者确认；不自动猜测白色区域是不是背景。比较要求图像模式一致，保护区比较还要求画布尺寸相同。探针只读输入，`--output`只允许新建JSON，不覆盖已有证据。

schema v2使用解码RGBA8和渲染元数据检查，支持`1/L/LA/P/RGB/RGBA`；不悄悄量化高位深/浮点/CMYK证据。它不做ICC转换、不保证显示器色彩，不判断产品结构或美观。没有请求具体检查时，总检查状态为`null`，不是通过。详情见[执行与验收](references/04-execution-and-audit.md)。

## 验证范围

自动化测试使用临时合成图片，覆盖确定性的脚本行为。组合场景属于人工语义检查，不是模型效果测试。本项目不声称覆盖所有商品结构，不以提示词出现“保真”或测试通过保证真实生图合格；缺少隐藏结构证据时应求原拍或说明限制。

贡献时请提供最小合成复现/匿名场景、预期行为和测试结果。不要上传客户原图、真实SKU清单、会话记录、私有路径、签名链接或凭据。

## License

[MIT](LICENSE) © 2026 M47E1。许可证适用于本仓库提供的代码与文档；仓库不包含客户照片、生产资产或私有项目记录，也不授予第三方图片/商标权利。Pillow作为外部依赖遵循其自身许可证。

MIT正文来源：[Open Source Initiative](https://opensource.org/license/mit)。
