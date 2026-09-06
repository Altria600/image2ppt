# Runtime Dependencies

Image2PPT 默认本地运行，不要求远程模型或全局 CLI。安装、渲染和跨平台状态要分开报告；“能构建”不等于“已完成视觉 QA”。

## Python 环境

建议 Python 3.10+ 虚拟环境：

### macOS / Linux

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r <image2ppt-root>/requirements.txt
./.venv/bin/python <image2ppt-root>/cli/image2ppt/cli.py doctor --json
```

### Windows PowerShell

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r <image2ppt-root>\requirements.txt
.venv\Scripts\python.exe <image2ppt-root>\cli\image2ppt\cli.py doctor --json
```

文档不声称 Windows 已在本项目中验收；请记录实际 Python、字体和 Office 渲染器版本。不要使用 pipx、系统级全局安装或另一个 Skill 代替当前目录的运行时。

基础 Python 包由 `requirements.txt` 定义，通常包括 pypdfium2、Pillow、NumPy、Requests、PyYAML 和 OpenAI（后者只在选定 API backend 时需要）。构建器直接写 OOXML，不依赖 `python-pptx`。

## 可选能力

- 本地 VTracer：`python -m pip install vtracer`。只在可追踪源路径时使用；未安装不阻塞原生对象或源稿局部资产路线。
- LaTeX 公式：本地 TeX engine；SVG 还需要 `dvisvgm` 或 `pdf2svg`，PNG 需要 ImageMagick。公式工具缺失是公式页硬失败，除非有具体用户批准。
- ImageMagick：只作少量格式/公式辅助；Pillow 是主要本地图像处理器。
- CJK 字体：按目标环境安装可用字体（例如 Noto Sans CJK 或 Microsoft YaHei），但不要假设字体名称在所有系统可用。

## Office 和渲染器

- macOS/Linux 常用 LibreOffice/`soffice` 做输入转换和 render。
- Windows 常用 PowerPoint 自动化或 LibreOffice；本仓库不把任一方式视为已验证的普适结果。
- WPS 不是默认 renderer，也未在本项目中声明通过；需要在目标 WPS 版本中手工打开、编辑、保存、重开并对照源图。
- 没有渲染器时，`page build`、OOXML/manifest 结构检查和部分静态校验仍可运行；页面必须保持 visual QA pending/unsupported，不能把结构通过写成渲染通过。
- 字体回退、SVG 支持、透明度、箭头和公式在 PowerPoint、LibreOffice 和 WPS 之间可能不同，最终以目标环境的实际 render 为准。

## 配置与网络边界

`config.yaml` 只放本机秘密，不能进入仓库或 run。默认不读取 `PADDLE_OCR_TOKEN`，也不发起 OCR 请求。只有用户明确在 `prepare`/`run hints` 传 `--allow-remote-ocr` 时，才读取 token 并上传当前任务数据；失败时保留本地几何提示并报告。

图像 backend 默认 `local-only`。主机图像工具、`builtin-imagegen`、`external-import`、OpenAI Images-compatible API 和 Codex OAuth 都必须显式选择，且失败不可静默切换。

先运行：

```bash
<python> <image2ppt-root>/cli/image2ppt/cli.py doctor --json
```

`doctor` 只报告本地依赖、renderer、字体、VTracer/公式工具和已配置能力的 set/unset 状态；不读取或打印秘密，不因“有 token”而上传。
