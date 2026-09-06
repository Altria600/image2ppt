# OCR and Text Hints Contract

文本提示用于测量和定位，不替代 agent 对源图字符的核对。默认走本地 `builtin-ink`：不读取 Paddle token、不上传页面、不因 token 存在而联网。

## 显式远程 OCR

只有用户明确允许远程 OCR 时，才在命令中传 `--allow-remote-ocr`：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py prepare input.pdf \
  --allow-remote-ocr
python <image2ppt-root>/cli/image2ppt/cli.py run hints <run-dir> \
  --allow-remote-ocr
```

远程路径读取本地 `PADDLE_OCR_TOKEN`，只发送当前任务必须的页面数据。配置 token 不等于授权上传；不传开关时必须保持本地路径。网络失败不触发其他远程服务，也不覆盖已存在的本地 hints。

当前远程实现若使用 PaddleOCR，应在运行输出中记录 endpoint/model 的实际值；不要把 token、响应中的私密内容或机器路径写入日志。Windows/macOS、服务配额和网络可用性没有在本项目中宣称已验证。

## 本地测量与使用

`prepare` 为每页生成 `text_hints.json` 和可选的 `text_hints.png`。每条提示包含源像素 `box_px`、字高、行数、CJK/Latin 字号候选、`size_group` 和生成 backend。提示可能漏字、合并行或误把图形当文字；最终文字以源图为准。

重生成单页提示：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py page hints <page-dir>
```

重生成整次运行提示：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run hints <run-dir>
```

只有显式的 `--allow-remote-ocr` 才允许以上 run-level 命令调用云端；没有该开关即使配置了 token 也使用本地测量。

## 文字所有权

- 主要标题、正文、数字、标签、表格文字和图表标签通常是原生文本框。
- Logo 字标、地图底图、截图内不要求编辑的小字、照片中的招牌等例外，要在 `visual_inventory` 或 `asset_provenance` 说明。
- 文字不能用生成图片、隐藏文本、透明文本、1 pt 文本或画外文本伪装成可编辑。
- 新页使用 `typography_policy: governed`，将提示中的测量框和字号与共享 `text_style_id`、`alignment_group`/`role` 对齐；溢出先修换行、框或整体同级样式。
