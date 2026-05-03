# Figstooffcie

Windows 桌面版图片处理工具。

第一期包含两个模块：

- 图片转 Word
- 图片转 Excel（单表识别）

## 运行

```bash
pip install -r requirements.txt
python main.py
```

## 目录

- `app/`：PySide6 桌面界面
- `core/`：通用模型、配置、任务执行
- `infra/`：模型调用、Word/Excel 导出
- `modules/`：业务模块

## 当前约束

- 只支持 Windows 桌面版
- 图片转 Word 的可编辑公式依赖本机 Microsoft Word 安装目录中的 `MML2OMML.XSL`
- 批处理架构支持并发，但默认并发数为 `1`
