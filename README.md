<div align="center">
  <h1>FormulaDoc</h1>
  <p><strong>面向 Windows 的 Office 文档转换工具</strong></p>
  <p>by Jorlin</p>
  <p>图片转 Word · 图片转 Excel · PDF 转 Word</p>
  <p>
    <a href="https://github.com/GeoHydrocarbon/FormulaDoc/releases">下载发布包</a>
    ·
    <a href="https://github.com/GeoHydrocarbon/FormulaDoc/tree/main/Figstooffcie#快速开始">快速开始</a>
    ·
    <a href="https://github.com/GeoHydrocarbon/FormulaDoc/tree/main/Figstooffcie#核心模块">模块说明</a>
    ·
    <a href="https://github.com/GeoHydrocarbon/FormulaDoc/issues">问题反馈</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?style=flat-square" alt="Windows">
    <img src="https://img.shields.io/badge/UI-PySide6-41CD52?style=flat-square" alt="PySide6">
    <img src="https://img.shields.io/badge/Word-DOCX-2B579A?style=flat-square" alt="DOCX">
    <img src="https://img.shields.io/badge/Table-XLSX-217346?style=flat-square" alt="XLSX">
    <img src="https://img.shields.io/badge/Input-Image%20%7C%20PDF-5C6BC0?style=flat-square" alt="Inputs">
  </p>
  <p>
    <a href="https://github.com/GeoHydrocarbon/FormulaDoc/releases">
      <img src="https://img.shields.io/badge/Download-Windows%20Build-0A66C2?style=for-the-badge" alt="Download">
    </a>
    <a href="https://github.com/GeoHydrocarbon/FormulaDoc/issues">
      <img src="https://img.shields.io/badge/Feedback-Issues-333333?style=for-the-badge" alt="Issues">
    </a>
  </p>
</div>

---

## 产品简介

FormulaDoc 的目标很直接：把图片或 PDF 中的文字、公式、表格恢复成可以继续编辑的 Office 文档，而不是只生成截图式结果。

当前提供 3 个核心能力：

- 图片转 Word：识别正文和公式，导出 `.docx`
- 图片转 Excel：识别单张表格图片，导出 `.xlsx`
- PDF 转 Word：重点保留文字、公式、表格，忽略图片

## 界面预览

<div align="center">
  <img src="Figstooffcie/docs/screenshots/main-window.png" alt="FormulaDoc 主界面" width="100%">
</div>

## 适合什么场景

- 论文截图、教材截图、扫描页整理成 Word
- 公式图片转可编辑公式
- 单表图片快速转 Excel
- 含文字、表格、公式的 PDF 转 Word

## 快速开始

1. 打开 [Releases](https://github.com/GeoHydrocarbon/FormulaDoc/releases)
2. 下载 Windows 发布包
3. 解压整个压缩包
4. 运行 `FormulaDoc.exe`
5. 在“设置”页填写自己的 `API Key`

## 仓库说明

- 桌面应用源码位于 [Figstooffcie/](https://github.com/GeoHydrocarbon/FormulaDoc/tree/main/Figstooffcie)
- 当前可执行程序和工程目录沿用 `Figstooffcie` 命名
- 根目录保留了一些早期脚本和实验文件

## 下一步

- 增强 PDF 中复杂公式和复杂表格的恢复质量
- 继续补充更多输入模块
- 完善发布流程和版本管理
