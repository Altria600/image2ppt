# Source Fidelity and Visual Style Contract

此合同用于 PDF、图片型页面和复杂局部，确保“来源”和“编辑性”不被混为一谈。

## 先看可用源结构

- PDF 有真实文字或 vector path 时，先检查并提取这些结构；不要无条件整页栅格化。
- 以最终可见源图为 z-order 与组合参考，不恢复被覆盖的旧底图来改变观感。
- 简单卡片、线、圆、连接器和表格骨架用原生对象。
- 复杂照片、纹理、插画和数据不可恢复的局部优先从源稿提取真实边界，记录 `source-extracted`；只有提取不足或遮挡修复才选择显式图像工具，记录 `image-edited` 与 `transform: image-edit`。
- 忠实扁平图标可用 `svg-reconstructed`；可追踪源路径可用本地 `vector-traced`。两者都是 `svg-image`，不宣称为原生 PPT 路径。

整页、整卡、整表或整图表不能作为图片底层绕过对象重建。复杂视觉不能被重绘成主题相近但身份不同的资产。

## 统一视觉语言

同一页有多个被编辑或生成的资产时，记录一个源稿一致的 style anchor：主体、视角、光照、色板、描边/边缘、透明行为和细节等级。先校准一个代表性局部，再处理其余需要 image-edit 的资产；源稿身份优先于“更漂亮”的重绘。

图像工具只处理用户已授权的必要输入；local-only 不联网。每个资产仍需在 manifest 和 provenance 中记录实际来源，实际 PowerPoint/LibreOffice render 才是构图、层级和风格验收证据。
