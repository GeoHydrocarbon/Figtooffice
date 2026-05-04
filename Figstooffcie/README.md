# Figstooffcie

Windows 桌面版文档处理工具。

当前包含三个模块：

- 图片转 Word
- 图片转 Excel（单表识别）
- PDF 转 Word

主要能力：

- 图片转 Word：支持正文、公式识别，导出带可编辑公式的 `.docx`
- 图片转 Excel：支持单表识别，导出 `.xlsx`
- PDF 转 Word：重点保留文字、公式、表格，忽略图片
- 输入方式：文件选择、目录批量、拖拽，图片模块额外支持剪贴板粘贴

## 运行

```bash
pip install -r requirements.txt
python main.py
```

## Windows 可执行程序（打包）

在 `Figstooffcie` 目录下使用已安装依赖的 Python（推荐本仓库的 `conda_env`）：

```powershell
.\build_windows.ps1
```

生成结果在 **`dist\Figstooffcie\`**：请**整夹复制**分发（`Figstooffcie.exe` 与同目录下 `_internal` 等文件须保持相对路径不变）。

当前 `requirements-build.txt` 只用于打包环境。`build_windows.ps1` 会：

- 检查并安装 `PyInstaller`
- 清理会阻塞打包的旧缓存
- 使用 `Figstooffcie.spec` 构建 Windows `onedir` 包

当前瘦身后的分发目录大约 `213 MB`。

打包前请**关闭正在运行的 `Figstooffcie.exe`**，否则 `--clean` 可能因文件占用而失败。

## 分发建议

- 发给别人时，直接压缩并分发整个 `dist\Figstooffcie\` 目录
- 不要只发送单个 `Figstooffcie.exe`
- 首次运行时，用户只需要在“设置”页填写自己的 API Key
- 本仓库不会提交 `conda_env/`、`build/`、`dist/`、`.localdata/` 等本地产物

## 公式说明

- 可编辑公式转换使用仓库内置的 `infra/equation/MML2OMML.XSL`
- 打包后的程序会随包携带该文件
- 不再要求目标机器单独安装 Microsoft Word 才能找到这份 XSL

## 目录

- `app/`：PySide6 桌面界面
- `core/`：通用模型、配置、任务执行
- `infra/`：模型调用、Word/Excel/PDF 处理
- `modules/`：业务模块

## 当前约束

- 只支持 Windows 桌面版
- PDF 转 Word 第一版采用“原生提取 + 视觉识别回退”的混合策略
- 批处理架构支持并发，但默认并发数为 `1`
- 图片转 Excel 第一版只支持单表识别
