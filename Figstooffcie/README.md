<div align="center">
  <h1>Figstooffcie</h1>
  <p><strong>Windows 桌面版文档处理工具</strong></p>
  <p>图片转 Word · 图片转 Excel · PDF 转 Word</p>
  <p>
    <a href="https://github.com/GeoHydrocarbon/Figtooffice/releases">下载发布包</a>
    ·
    <a href="#快速开始">快速开始</a>
    ·
    <a href="#核心模块">核心模块</a>
    ·
    <a href="https://github.com/GeoHydrocarbon/Figtooffice/issues">问题反馈</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?style=flat-square" alt="Windows">
    <img src="https://img.shields.io/badge/UI-PySide6-41CD52?style=flat-square" alt="PySide6">
    <img src="https://img.shields.io/badge/PDF-Native%20%2B%20Vision-5C6BC0?style=flat-square" alt="PDF">
    <img src="https://img.shields.io/badge/Clipboard-Image%20Input-FF9800?style=flat-square" alt="Clipboard">
  </p>
  <p>
    <a href="https://github.com/GeoHydrocarbon/Figtooffice/releases">
      <img src="https://img.shields.io/badge/Download-Windows%20Build-0A66C2?style=for-the-badge" alt="Download">
    </a>
    <a href="https://github.com/GeoHydrocarbon/Figtooffice/issues">
      <img src="https://img.shields.io/badge/Feedback-Issues-333333?style=for-the-badge" alt="Issues">
    </a>
  </p>
</div>

---

## 核心模块

- 图片转 Word：识别正文和公式，导出带可编辑公式的 `.docx`
- 图片转 Excel：识别单表图片，导出 `.xlsx`
- PDF 转 Word：优先保留文字、公式、表格，当前默认忽略图片

## 界面预览

<div align="center">
  <img src="docs/screenshots/main-window.png" alt="Figstooffcie 主界面" width="100%">
</div>

## 输入方式

- 文件选择
- 目录批量
- 拖拽输入
- 图片模块支持剪贴板粘贴

## 快速开始

### 直接使用打包程序

1. 打开 [Releases](https://github.com/GeoHydrocarbon/Figtooffice/releases)
2. 下载 Windows 发布包
3. 解压整个压缩包
4. 运行 `Figstooffcie.exe`
5. 在“设置”页填写自己的 `API Key`

### 本地运行源码

```bash
pip install -r requirements.txt
python main.py
```

## Windows 可执行程序（打包）

在 `Figstooffcie` 目录下使用已安装依赖的 Python：

```powershell
.\build_windows.ps1
```

打包结果输出到 `dist\Figstooffcie\`，分发时需要**整个目录一起发送**，不要只发送单个 `Figstooffcie.exe`。

当前瘦身后的分发目录大约 `213 MB`，压缩包大约 `92 MB`。

## 分发建议

- 首次运行时，用户只需要在“设置”页填写自己的 `API Key`
- 仓库不会提交 `conda_env/`、`build/`、`dist/`、`.localdata/` 等本地产物
- 如果重新打包，请先关闭正在运行的 `Figstooffcie.exe`

## 公式说明

- 可编辑公式转换使用仓库内置的 `infra/equation/MML2OMML.XSL`
- 打包后的程序会随包携带该文件
- 不再要求目标机器单独安装 Microsoft Word 才能找到这份 XSL

## 目录结构

- `app/`：PySide6 桌面界面
- `core/`：通用模型、配置、任务执行
- `infra/`：模型调用、Word/Excel/PDF 处理
- `modules/`：业务模块

## 当前约束

- 只支持 Windows 桌面版
- PDF 转 Word 当前采用“原生提取 + 视觉识别回退”的混合策略
- 批处理架构支持并发，但默认并发数为 `1`
- 图片转 Excel 第一版只支持单表识别
