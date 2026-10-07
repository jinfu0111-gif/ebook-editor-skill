# 参考来源与工具选型

核查日期：2026-10-07。使用涉及设备、转换器或规范版本的细节时再查当前官方文档，不把本页日期当作长期有效保证。本文以链接和自主整理为主，不转载教程全文或第三方代码。

## 官方规范和操作文档

- [W3C EPUB 3](https://www.w3.org/TR/epub/)：OPF、OCF、导航、资源和内容文档规范。先确认目标格式版本。
- [EPUBCheck](https://github.com/w3c/epubcheck)：DAISY 为 W3C 维护的规范校验器；官方发布下载和用法以仓库为准。本 Skill 的 Python 检查是补充。
- [DAISY Notes](https://kb.daisy.org/publishing/docs/html/notes.html)：注释语义、引用和可访问性。
- [Calibre 编辑器](https://manual.calibre-ebook.com/edit.html)、[格式转换](https://manual.calibre-ebook.com/conversion.html)：编辑 EPUB/AZW3、目录、封面、链接、转换及预览。
- [Pandoc EPUB](https://pandoc.org/MANUAL.html#epub-metadata)：从 Markdown/结构化内容创建 EPUB、元数据及样式。
- [Kindle 流式文本指南](https://kdp.amazon.com/en_US/help/topic/GH4DRT75GWWAGBTU)：正文读者设置、脚注双向链接和语义、真实页码。
- [Kobo EPUB 说明](https://github.com/kobolabs/epub-spec)：Kobo 特定兼容性，包括注释行为。
- [Tesseract 输出格式](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)：hOCR/TSV 等位置数据。

## 书伴：中文实践教程

- [排版制作专题](https://bookfere.com/category/skills/typesetting)
- [Sigil 从零制作 EPUB](https://bookfere.com/post/73.html)
- [一般最佳实践](https://bookfere.com/post/601.html)
- [流式电子书、脚注及样式](https://bookfere.com/post/610.html)
- [弹出脚注/尾注](https://bookfere.com/post/285.html)
- [Sigil + EPUBCheck 检查和修复](https://bookfere.com/post/1004.html)

书伴适合中文操作理解和排版实例。较早文章的 KindleGen、MOBI 或固件说明应按当年的环境理解；当前 EPUB 3 或设备行为以官方规范和实际测试为准。帖子评论是读者个案，不是跨设备保证。

## 开源比较与复用决定

| 项目 | 所核查的许可证 | 本 Skill 如何使用 |
| --- | --- | --- |
| [EPUBCheck](https://github.com/w3c/epubcheck) | BSD-3-Clause | 直接调用已安装的官方校验器，不重新实现完整 EPUB 规范 |
| [Sigil](https://github.com/Sigil-Ebook/Sigil) | GPL-3.0 | 可选外部编辑器，不内嵌源代码或二进制 |
| [Pandoc](https://github.com/jgm/pandoc) | GPL-2.0，细则见其许可证 | 优先用于结构化文稿转换，不自建通用 Markdown 转换器 |
| [EbookLib](https://github.com/aerkalov/ebooklib) | AGPL-3.0 | 有明确编程需求且环境已有时可评估；不作为随附工具依赖 |
| [magnus919/agent-skills 的 EPUB Skill](https://github.com/magnus919/agent-skills/tree/main/epub) | 仓库及 Skill 标注 MIT | 参考工具分工和非破坏编辑思路；未复制其代码或文档 |

上述工具仓库在核查时均可访问且未归档。社区 Skill 更新不等于所有规则经过验证，尤其不能把某阅读器测试结论提升为 EPUB 通用规范。采用的库、字体或工具若需要再分发，应查看其完整许可证。

随附 Python 代码在本项目内维护，只有标准库依赖；第三方程序由其各自许可证和发行渠道负责。这样安装基础检查能力不需要下载大型转换、OCR 或模型组件。
