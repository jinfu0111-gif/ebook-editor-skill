# Ebook Editor Skill · v0.1

一个可分享的电子书制作与修订 Skill，适用于支持 `SKILL.md` 的 AI 编程助手。覆盖 EPUB 2/3、扫描 PDF 的 OCR 可重排重建、目录与脚注、书籍信息、样式修订和阅读器兼容性；MOBI/AZW3 通过可用的 Calibre 转换。

Portable ebook creation and editing skill. Includes dependency-free Python tools for EPUB packaging and targeted audits, plus workflows for OCR reconstruction, source proofreading, semantic notes, and reader-adjustable typography.

## 能做什么

- 检查和修复 EPUB 包结构、目录、阅读顺序和资源链接。
- 修改封面、简介、作者/译者、出版日期、出版社及 ISBN。
- 排查字体粗细不统一、行距不能调节、脚注链接和弹出兼容性。
- 从扫描 PDF 重建可重排电子书：保留 OCR 位置数据，审核跨页段落、正文/引文边界、角标和标点。
- 复用 Pandoc、Calibre、Sigil 和 EPUBCheck，按需转换格式。

OCR 流程需要环境中可用的 OCR 和 PDF 工具；本仓库没有内置模型，也不承诺一键生成无误的全文。脚注弹出效果由阅读器决定，包含普通链接回退。内置审计不是 EPUBCheck，也不证明 OCR 文字准确。

## 安装

Skill 目录就是仓库根目录。克隆到你的 Skill 搜索路径，或下载仓库后复制整个目录并命名为 `ebook-editor`。

Codex 的常见用户目录安装示例：

```sh
git clone https://github.com/jinfu0111-gif/ebook-editor-skill.git ~/.codex/skills/ebook-editor
```

Windows PowerShell：

```powershell
git clone https://github.com/jinfu0111-gif/ebook-editor-skill.git "$env:USERPROFILE/.codex/skills/ebook-editor"
```

若已有同名 Skill，安装到另一目录后比较，避免覆盖已有修改。若配置了不同的 Skill 目录，使用该配置。其他助手使用各自支持的 Skill 目录；`agents/openai.yaml` 是可选 Codex 显示信息，不是运行依赖。

## 使用

在助手中说明输入、输出和目标阅读器，例如：

> 使用 $ebook-editor 修复这本 EPUB 的目录和字体粗细，保留原文件，输出 v0.1。

> 使用 $ebook-editor 将这个扫描 PDF 做成 OCR 可重排 EPUB。先验证代表性页面，再扩展到全书，对照原 PDF 审核引文边界和脚注位置，列出待核实内容。

> 使用 $ebook-editor 排查这本 EPUB 在我的阅读器中不能调节行距的问题，并保留脚注回链。

## 命令行工具

Python 3.10+，基础工具无须 `pip install`。在仓库根目录运行：

```sh
python scripts/epub_archive.py inspect input.epub --json
python scripts/epub_archive.py extract input.epub work/book
python scripts/epub_archive.py pack work/book output-v0.1.epub
python scripts/epub_audit.py output-v0.1.epub --json
```

解包拒绝非空目的目录；打包拒绝已存在的输出。损坏包可在检查后使用 `extract --allow-invalid` 修复，ZIP 路径、安全和大小检查仍保留。审计只读取本地文件，不访问外部链接。

退出码：`0` 为所检查范围无错误（仍可有警告），`1` 为检查/审计报告存在错误（包括输入不可读）；解包/打包执行失败及命令参数错误使用 `2`。所有警告需要结合书籍设计判断；例如局部引文字体可能有意设置。

可选工具：Calibre（转换/元数据/编辑）、Pandoc（结构化文稿）、EPUBCheck + Java（规范验证）、PDF 渲染器和 OCR 后端（扫描来源）。根据任务发现和复用已有环境；本 Skill 不自动安装外部组件。

## 目录

```text
SKILL.md                  助手入口和任务路由
agents/openai.yaml        Codex 显示信息
references/               工作流、OCR、格式及兼容性说明
scripts/epub_archive.py   EPUB 检查、解包、打包
scripts/epub_audit.py     内容链接、脚注及 CSS 兼容性提示
assets/                   原创 CSS 和脚注示例
tests/                    合成样例和工具回归检查
```

运行回归测试：

```sh
python -m unittest discover -s tests -v
```

样例为原创合成文本，不包含真实书籍、扫描件、私人路径、字体文件、认证配置或 OCR 模型。仓库 CI 在 Windows 和 Linux 上执行 Python 检查。

## 来源与许可

本 Skill 使用 MIT 许可证。参考了[书伴的制作教程](https://bookfere.com/category/skills/typesetting)，并以 W3C、DAISY、Calibre 和目标阅读器的官方资料核对实现。链接、许可证评估和复用选择见 [sources.md](references/sources.md)。第三方工具和用户书籍各自保留其原有许可；本仓库许可不覆盖它们。

欢迎通过 Issue 提供问题：输入格式、工具/阅读器版本、实际现象、预期现象和最小可分享样例。请使用你有权分享的原创或公开样例，避免附上整本受版权保护的书籍。
