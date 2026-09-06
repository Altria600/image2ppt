<div align="center">
  <p><img src="assets/readme/hero-zh.svg" alt="让每一页，重新可编辑。" width="960"></p>
  <h1>Image2PPT</h1>
  <p>从一张静态图片，回到可以继续修改的演示文稿。</p>
  <p>
    <a href="https://github.com/Altria600/image2ppt/releases/tag/v1.3.0"><img alt="Release" src="https://img.shields.io/badge/release-v1.3.0-2563eb"></a>
    <a href="https://github.com/Altria600/image2ppt"><img alt="Stars" src="https://img.shields.io/github/stars/Altria600/image2ppt?style=flat"></a>
    <a href="https://github.com/Altria600/image2ppt/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Altria600/image2ppt/actions/workflows/ci.yml/badge.svg"></a>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-2ea44f"></a>
  </p>
  <p>
    <a href="#开始使用"><img alt="Install" src="https://img.shields.io/badge/install-Codex%20%7C%20WorkBuddy-1D6653"></a>
    <a href="README_EN.md">English</a>
  </p>
</div>

一页旧方案、一张科研示意图、一份只剩扫描件的资料。你想改的，往往只是一个字、一根箭头，或一个数字。

**Image2PPT，让这些修改重新成为可能。**

把图片、扫描 PDF 或图片型 PPT 交给 Agent，它会按页面结构重建文字、形状与独立素材，再生成可编辑的 PPTX。留下原稿的内容与关系，也为下一次修改留下空间。

<p align="center">
  <a href="https://github.com/Altria600/image2ppt/releases/download/v1.3.0/image2ppt-portable-1.3.0.zip">下载 v1.3.0 便携包</a>
  ·
  <a href="#开始使用">快速开始</a>
  ·
  <a href="#案例先看复杂页面">查看案例</a>
</p>

## 案例：先看复杂页面

从商业长图里的时间线、卡片与文字，到科研图中的节点、箭头与插画，重建的重点始终是：**保留关系，找回可以单独修改的对象。**

<table>
  <tr>
    <td align="center" width="50%"><strong>商业页面 · 源图</strong><br><img src="assets/readme/business-source.png" alt="商业页面源图" width="100%"></td>
    <td align="center" width="50%"><strong>商业页面 · 重建</strong><br><img src="assets/readme/business-converted.png" alt="商业页面重建结果，显示可选择对象" width="100%"></td>
  </tr>
  <tr>
    <td align="center" width="50%"><strong>科研图 · 源图</strong><br><img src="assets/readme/scientific-source.png" alt="科研图源图" width="100%"></td>
    <td align="center" width="50%"><strong>科研图 · 重建</strong><br><img src="assets/readme/scientific-converted.png" alt="科研图重建结果，显示可选择对象" width="100%"></td>
  </tr>
</table>

<sub>以上为仓库既有案例，不是 v1.3.0 新测。右侧选框展示对象选择状态，放映时不会出现；可点击图片查看大图。不同输入的还原效果，以实际对照验收为准。</sub>

<details>
<summary>查看历史案例的局部放大对照</summary>

<p align="center"><img src="assets/readme/clarity-comparison.png" alt="历史案例的局部清晰度对照" width="100%"></p>
<p align="center"><img src="assets/readme/detail-comparison.png" alt="历史案例的复杂关系与细节对照" width="100%"></p>

</details>

## 能改到哪一步

简单的地方，保留编辑自由；复杂的地方，保留原稿质感。

| 页面对象 | PPTX 中的结果 | 你可以怎样继续编辑 |
| --- | --- | --- |
| 文字、卡片、表格结构、普通箭头 | 原生文本框、形状与连接线 | 改字、改色、移动、调整大小与连线 |
| 扁平图标、可描摹的局部轮廓 | 独立 SVG 矢量图片 | 移动、缩放、替换；需要细改时编辑随附 SVG |
| 照片、3D、光影与复杂插画 | 保留原稿身份的独立图片 | 单独移动、调整与替换，保留复杂视觉细节 |

同一页可以混用这三种方式。复杂素材优先从原稿分离，只有提取不足或需要修复遮挡时，才使用已授权的图像编辑工具。SVG 图片不等于 PowerPoint 原生路径，交付时会说明实际可编辑范围。

## 开始使用

### 先选一种入口

- **下载便携包**：获取 [image2ppt-portable-1.3.0.zip](https://github.com/Altria600/image2ppt/releases/download/v1.3.0/image2ppt-portable-1.3.0.zip)，解压后把整个目录交给宿主 Agent 使用。
- **Codex repo skill**：把本目录（或解压后的便携包目录）复制到目标项目的 `.agents/skills/image2ppt/`，不做全局安装。
- **WorkBuddy**：下载上面的便携 ZIP，在技能页面通过本地技能包导入。自定义版本也可以在仓库根目录运行下面的打包命令。

```bash
python3 scripts/package_skill.py --output dist/image2ppt.zip
```

### 第一次运行

安装 Skill 后，可以直接把这段话发给 Agent：

```text
使用 image2ppt，把我提供的图片或 PDF 还原为可编辑 PPTX。
保留原稿版式；文字、卡片和普通箭头独立可编辑；
简单图标用 SVG，复杂插画尽量保留原稿；
先用本地能力，调用外部服务前说明范围，完成实际渲染核对后交付。
```

建议使用项目内 Python 3.10+ 虚拟环境，不依赖全局 `image2ppt` 命令：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python cli/image2ppt/cli.py doctor --json
./.venv/bin/python cli/image2ppt/cli.py prepare input.pdf \
  --out-root output/image2ppt --image-backend local-only
```

`prepare` 负责建立本次输入和页面运行目录；完整的逐页重建、构建、渲染 QA、记录和最终装配，按 [SKILL.md](SKILL.md) 的页面生命周期执行。输入也可以是图片或图片型 PPT/PPTX。

<details>
<summary>macOS：源码方式的完整步骤</summary>

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python cli/image2ppt/cli.py doctor --json
./.venv/bin/python cli/image2ppt/cli.py prepare /path/to/input.pdf \
  --out-root output/image2ppt --image-backend local-only
```

需要视觉验收时，在目标机器安装并使用 LibreOffice；本仓库本次 v1.3.0 已在 macOS + LibreOffice 完成真实 source → PPTX 验收。字体、SVG、透明度、箭头和公式仍应以最终使用环境的实际 render 为准。

</details>

<details>
<summary>Windows PowerShell：源码方式的完整步骤</summary>

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe cli\image2ppt\cli.py doctor --json
.venv\Scripts\python.exe cli\image2ppt\cli.py prepare C:\path\to\input.pdf `
  --out-root output\image2ppt --image-backend local-only
```

Windows、PowerPoint/WPS 和 WorkBuddy 的真实宿主验收尚未在本仓库完成；请记录目标机的 Python、字体、Office/renderer 版本和实际 render 结果。不要使用 `pipx`、系统级全局安装或另一个 Skill 代替当前目录的运行时。

</details>

## 路线图

先理解页面区域，再按对象测量和分流；最后把结构检查与实际渲染对照放在同一条交付链上。

<p align="center"><img src="assets/readme/routing-zh.svg" alt="Image2PPT 对象路由示意：源稿、对象分流、PPTX 与渲染验收" width="960"></p>

1. **读入源稿**：保留页面比例、顺序和必要的 speaker notes。
2. **测量与分流**：文字、卡片、表格和普通箭头走原生对象；扁平图标和可追踪路径走 SVG；复杂视觉保留有边界的原稿资产。
3. **构建与复核**：从 `manifest.json` 生成 PPTX，检查对象结构、来源记录、字体与溢出，再用实际 renderer 对照源图。

## 验证边界

<details>
<summary>打开 v1.3.0 的验证口径</summary>

- 本地完整回归：**217 tests passed**；后续路由、provider、package 和 metadata 的收尾复测：**62 项 targeted tests passed**（与完整套件有重叠）。
- 已验证：本地 Python 3.11、LibreOffice 渲染，以及真实 source → PPTX 的页面级流程；SVG PNG fallback、原稿局部提取守卫和原生测量箭头也有离线测试覆盖。
- 尚未声称：Windows/WorkBuddy 实际宿主、目标 PowerPoint/WPS 渲染、真实外部 OCR/图像 API 调用。CI 已准备 Windows/macOS 离线 job，远程运行结果以发布后的 workflow 为准。
- 没有 renderer 时，`page build`、manifest/OOXML 结构检查仍可运行，但不能把它们称作视觉 QA 通过；未验收页面必须明确保留为 pending/unsupported。

</details>

## 技术细节与配置

默认 backend 是 `local-only`：本地解析、原稿局部提取、SVG、可选 VTracer 和确定性构建，不读取未选择的凭据，也不联网。`host-image-tool`、`builtin-imagegen`、`external-import`、`openai-compatible-api` 和 `codex-oauth` 都必须显式选择，失败不会静默切换 provider。

`config.yaml` 只用于本机，Git 应忽略它；`IMAGE2PPT_CONFIG_HOME` 可指定配置目录。复制 [config.example.yaml](config.example.yaml) 后只填本地秘密：

```yaml
OPENAI_API_KEY: "你的 API Key"
OPENAI_BASE_URL: "https://服务地址/v1"
IMAGE2PPT_IMAGE_BACKEND: "openai-compatible-api"
IMAGE2PPT_IMAGE_MODEL: "供应商提供的模型 ID"
```

远程 OCR 默认关闭；只有明确允许时在 `prepare` 或 `run hints` 添加 `--allow-remote-ocr`。可选的本地 VTracer 安装为 `python -m pip install vtracer`。详细参数、字段和恢复路径见 [references/runtime-dependencies.md](references/runtime-dependencies.md)、[references/page-decision-tree.md](references/page-decision-tree.md)、[references/manifest-schema.md](references/manifest-schema.md) 和 [references/qa-contract.md](references/qa-contract.md)。

## 进一步阅读与许可

完整页面生命周期、单 Agent 多页串行方式和 worker ownership 见 [SKILL.md](SKILL.md) 与 [references/workflow.md](references/workflow.md)。

本地整合版以 [Altria600/image2ppt](https://github.com/Altria600/image2ppt) 为基础，保留上游 [Paul-Jeo/Image2PPT](https://github.com/Paul-Jeo/Image2PPT) 的 MIT 许可证与归属；Cell-lct 仅作为矢量处理流程参考，未复制其未声明许可的代码。

如果它帮你省下了一次重画，欢迎在 GitHub 点个 [Star](https://github.com/Altria600/image2ppt)，让更多人找回可编辑的原稿。

本项目采用 [MIT License](LICENSE)。
