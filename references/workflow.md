# Workflow and Run Contract

工作流只有一套运行状态和一套构建源。并发 worker 是可选优化；没有 delegation 时，main agent 通过相同的 CLI 逐页串行完成。

## 权威文件

| 阶段 | 权威文件/实现 |
| --- | --- |
| 输入归一化 | `prepare` 与 `cli/image2ppt/runtime/` |
| 文本提示 | `text_hints.json`/`text_hints.png`，仅作测量提示 |
| 页面状态 | `page_jobs.json` 与 `run` 子命令 |
| 页面 Prompt | `prompts/page-worker-base.md` + `prompts/page-worker.md` |
| 页面内容 | `pages/page_NNN/manifest.json` |
| 页面构建 | `page build` |
| 页面/最终 QA | `run_image2ppt_qa.py`、`run_final_image2ppt_qa.py` |
| 最终装配 | `run finalize` |

禁止另建 page plan、OCR 副本、controller、第二 manifest、第二装配器或替代 lifecycle。区域、来源和 QA 都写回标准 manifest 或 supplemental report。

## 生命周期

```text
prepare
  -> run next
  -> build_page_worker_prompt
  -> run dispatch (worker 或 --local)
  -> 页面 inventory/route/manifest
  -> page build + page validate + render QA
  -> run record
  -> run finalize
  -> final render/structure QA
```

### 多页与单 Agent

有并发能力时，只并行独立页面，按 `max_concurrent_pages` 和页面目录 ownership 分配。没有并发能力时同样支持多页：

1. `run next --json --local` 领取一个 pending page；JSON 中使用返回的 `next_argv` 数组，不要自行拼接含中文或空格路径的 `next_command`；
2. 生成该页 Prompt，并用 `run dispatch --local --agent-id main` 建立 lease；
3. 完成构建和 QA，再 `run record --agent-id main`；
4. 重复下一页，最后 `run finalize`。

一个 main agent 同时不能持有多个 local lease。页面完成后才领取下一页；不要手工改 `page_jobs.json`。

## 运行级不变量

1. `prepare` 复制输入、生成源页、`page_request.json`、`page_jobs.json`、文本提示和 speaker-note 清单。
2. `run next` 只读状态，给出 configure/dispatch/wait/finalize 建议；`--local` 让多页任务也逐页生成 local dispatch 建议。
3. `run dispatch` 记录 worker 或 local lease、Prompt hash、page request hash 和写入范围。
4. 已 dispatch 页面保持 active，除非 worker 明确完成、失败、取消或经确认已丢失；时间经过不自动 reset。
5. `run record` 校验页面产物、manifest 路径、结构、hash 和顶层 `validation.json.passed: true`。
6. `run reset` 是回到 pending 的唯一支持路径。修复页重新 dispatch；已记录页不能直接改 final PPTX。
7. `run finalize` 只读取已记录 manifest，按页序重建最终 deck，恢复 speaker notes，并在同一 run 内原子发布。

## Backend 与网络

每个 run 的 `image_backend` 原样复制到 `page_request.json`。默认 `local-only`；`host-image-tool` 必须有显式工具名/调用名；`builtin-imagegen`、`external-import`、`openai-compatible-api`、`codex-oauth` 都是显式选择。工具失败不静默 fallback；记录 blocked 原因，并保留已经完成的其他页面。

远程 OCR 只有用户在当前 `prepare` 或 `run hints` 命令中明确传 `--allow-remote-ocr` 才能执行；授权不写入 `page_request.json` 或其他持久状态。普通 prepare/run hints 不读取 token、不上传页面。

## 备注、失败与验收

`prepare` 是唯一 speaker-note 提取阶段；页面 worker 不读取、改写或删除 notes。`run finalize` 是唯一装配阶段。

如果某页缺少 renderer，允许先构建和做结构校验，但该页的视觉 review 必须保持 pending/unsupported；不能通过复制旧 evidence 或 free-text 关闭门禁。若 QA 失败，修复页面 manifest/assets，按 `run reset` → dispatch → record → finalize 重做。不要只改最终 PPTX。
