# Figstooffcie

Windows 桌面版文档处理工具。

当前包含三个模块：

- 图片转 Word
- 图片转 Excel（单表识别）
- PDF 转 Word

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

生成结果在 **`dist\Figstooffcie\`**：请**整夹复制**分发（`Figstooffcie.exe` 与同目录下 `_internal` 等文件须保持相对路径不变）。首次打包会安装 `requirements-build.txt` 中的 PyInstaller。

说明：当前 `Figstooffcie.spec` 使用 `collect_all('PySide6')` 以尽量保证 Qt 插件齐全，体积会较大；若仅需图形界面核心模块，可自行改为依赖 PyInstaller 默认 hook 以减小体积（需自行回归测试）。

打包前请**关闭正在运行的 `Figstooffcie.exe`**（并尽量不要在资源管理器中打开 `dist\Figstooffcie\_internal`），否则 `--clean` 可能因文件被占用而失败。`latex2mathml` 所需的 `unimathsymbols.txt` 已由 `Figstooffcie.spec` 打入 `_internal\latex2mathml\`。

## 目录

- `app/`：PySide6 桌面界面
- `core/`：通用模型、配置、任务执行
- `infra/`：模型调用、Word/Excel/PDF 处理
- `modules/`：业务模块

## 当前约束

- 只支持 Windows 桌面版
- 图片转 Word 的可编辑公式依赖本机 Microsoft Word 安装目录中的 `MML2OMML.XSL`
- PDF 转 Word 第一版采用“原生提取 + 视觉识别回退”的混合策略
- 批处理架构支持并发，但默认并发数为 `1`
