# tools/deploy —— allin 部署运维物（Windows 计划任务 + 每日备份 + 月度治理盘点）

> 依据：P3 部署实施方案（team 工作区）· 拍板口径 2026-11-04（4 任务 + 备份根异盘）。
> 2026-11-07 增量：ERP 调研 P2 备用路线落地第 5 个任务 `ALLIN-monthly-audit`。
> 2026-11-08 增量：审查残留 #21「月度恢复演练调度」落地第 6 个任务 `ALLIN-monthly-restore-drill`（仓内计划任务配方，不落 CI schedule）。
> 纪律：本目录内脚本**零盘符字面量**（g01 门禁）——真实路径一律 env（`ALLIN_ROOT` / `ALLIN_BACKUP_ROOT` / `ALLIN_LOG_DIR` / `ALLIN_PYTHON`）或注册期实参注入；`.ps1` 全部 UTF-8 BOM（check_ps1_bom 门禁）。

## 文件清单

| 文件 | 职责 |
|---|---|
| `backup-allin.ps1` | 每日备份：website 库 wal_checkpoint(TRUNCATE) → robocopy /MIR platform/data 与 website/data（排除 keys 与种子口令文件）→ manifest.json（逐文件 sha256 + robocopy 退出码 <8 判定）→ 按目录名 7 天轮转 → 运行日志 14 天清理 |
| `exclusion-policy.ps1` | 共享排除策略单一真相源：敏感材质清单（keys / 种子口令 / `*.pem` / `.env` / `credentials.json` 等）+ robocopy 排除参数；`backup-allin.ps1` / `restore-allin.ps1` / `test_restore_drill.ps1` 三方 dot-source 它 ⇒ **四文件须同在 `tools\deploy\`**（缺文件即 fail-loud） |
| `start-website-task.ps1` | 计划任务包装器：登录拉起 website 常驻（9042），按日重定向日志，Node ≥22.5 前置校验，退出码透传 |
| `start-portal-task.ps1` | 计划任务包装器：登录拉起 portal 常驻（PORT=0 临时端口 + data/portal.port 文件发现，零新增常驻端口） |
| `monthly_audit.py` | **月度治理盘点器**（纯标准库）：`verify_facts` + `docs_index(D1–D17)` + repocheck + 组合分级表内自洽对账；月度幂等守卫 + JSONL 留痕 + `--selfcheck` 夹具 |
| `monthly-audit-task.ps1` | 任务⑤ 包装器：仓根自发现 + Python 解析链 + 控制台编码临时切 UTF-8（防中文日志乱码）+ 日志按日落 + 退出码透传 |
| `restore-drill-task.ps1` | 任务⑥ 包装器：把 `test_restore_drill.ps1` 当**子进程**启动（脚本内部 `exit`，直接 `&` 会连包装器一起终止）+ 月度幂等守卫 + JSONL 留痕 + 日志按日落 + 退出码透传；只证明演练脚本逻辑按月回归，**不替代人工 SEV1 全链演练** |
| `register-tasks.ps1` | 注册 6 个 ALLIN-* 计划任务（website / portal / daily-backup / weekly-e2e / monthly-audit / monthly-restore-drill）；`-Unregister` 一键回滚 |

## 安装（一次性，全部免管理员）

```powershell
# 1) 用户级 env（对新开进程生效；<REPO_ROOT> / <BACKUP_ROOT> 按本机实际填写，
#    盘符只出现在本机命令与任务计划参数中，不进仓内任何文件）
setx ALLIN_ROOT        "<REPO_ROOT>"
setx ALLIN_BACKUP_ROOT "<BACKUP_ROOT>"        # 备份根必须与数据所在盘异盘（同机异盘底线）
setx ALLIN_LOG_DIR     "<LOG_DIR>"            # 可省；缺省 <LOCALAPPDATA>\allin\logs

# 2) 确认部署物在位后注册 6 个计划任务（在 powershell 中运行）
powershell -NoProfile -ExecutionPolicy Bypass -File "<REPO_ROOT>\tools\deploy\register-tasks.ps1"
```

注册完成后验证：

```powershell
Get-ScheduledTask -TaskName "ALLIN-*" | Format-Table TaskName,State
Get-ScheduledTaskInfo -TaskName ALLIN-website-autostart,ALLIN-portal-autostart,ALLIN-daily-backup,ALLIN-weekly-e2e,ALLIN-monthly-audit,ALLIN-monthly-restore-drill |
  Format-Table TaskName,LastRunTime,LastTaskResult
```

## 用法

**手动跑一次备份**（先看产物再信任计划任务）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<REPO_ROOT>\tools\deploy\backup-allin.ps1" -BackupRoot "<BACKUP_ROOT>"
```

- 产物：`<BACKUP_ROOT>\<yyyy-MM-dd>\{platform-data\, website-data\, manifest.json}`；
  恢复只认 `manifest.json` 中 `status:"ok"` 的目录，恢复顺序 = 先 restore-key（website 密钥包）后拷 site.db 三件套（P3 §4.1）。
- 密钥**不走本脚本**：`website/data/keys` 被 `/XD keys` 排除；密钥灾备唯一通道 = website 的 `npm run backup-key` / `restore-key`（月度恢复演练）。
- checkpoint 失败（如 Node < 22.5）默认 fail-loud；确认 website 已停止时可 `-SkipCheckpoint` 跳过（manifest 如实标记 `skipped`）。

**试跑 / 停启 / 回滚任务**：

```powershell
Start-ScheduledTask  -TaskName ALLIN-daily-backup          # 手动试跑备份
Start-ScheduledTask  -TaskName ALLIN-monthly-audit         # 手动试跑月度盘点（同月已 ok 会 skip）
Start-ScheduledTask  -TaskName ALLIN-monthly-restore-drill # 手动试跑月度恢复演练（同月已 ok 会 skip）
Stop-ScheduledTask   -TaskName ALLIN-website-autostart     # 停常驻（恢复演练等场景）
powershell -NoProfile -ExecutionPolicy Bypass -File "<REPO_ROOT>\tools\deploy\register-tasks.ps1" -Unregister
```

**监控最小化三件套**（P3 §6）：① `Get-ScheduledTaskInfo`（上方命令，含任务⑤/⑥）② 探活 `curl http://127.0.0.1:9042/healthz` + 读 `platform/data/portal.port` 探 portal + `python allin_cli.py status` ③ 周度 `ALLIN-weekly-e2e` 自动跑 `npm run smoke:e2e`。月度盘点结果另见 `ALLIN-monthly-audit` 的 `LastTaskResult` 与下方 JSONL；月度恢复演练结果见 `ALLIN-monthly-restore-drill` 的 `LastTaskResult` 与 `tools/gate/audit/restore-drill-runs.jsonl`（非 0 即演练失败，须复验）。

## 月度治理盘点（ERP 调研 P2 备用路线，2026-11-07）

**为什么不在 WorkBuddy 里做**：会话侧定时自动化绑定某台机器的工作区，换机即失效、配方不随仓库 clone 复制。本路线把配方压进仓内：判据复用 `tools/facts/` / `tools/gate/`，调度由 Task Scheduler 承担，**注册动作仍由人在各机执行**（ADR-0010 部署守护面同款纪律），不依赖 npm / bash / WorkBuddy。

**跨机复制三步**（每台机器只做一次）：

```powershell
# 1) clone / pull 本仓后设置仓根（盘符只出现在本机命令里，不进仓内文件）
setx ALLIN_ROOT "<REPO_ROOT>"
# 2) 注册 6 个任务（含任务⑤/⑥）；-MonthlyAt 改任务⑤ 时刻（缺省周一 09:00），-DrillAt 改任务⑥ 时刻（缺省周一 10:00，与任务⑤ 错开一小时）
powershell -NoProfile -ExecutionPolicy Bypass -File "<REPO_ROOT>\tools\deploy\register-tasks.ps1"
# 3) 手工首跑一次，先看产物再信任计划任务
powershell -NoProfile -ExecutionPolicy Bypass -File "<REPO_ROOT>\tools\deploy\monthly-audit-task.ps1" -Force
```

手动等价命令（不经计划任务）：

```powershell
python "<REPO_ROOT>\tools\deploy\monthly_audit.py" --repo-root "<REPO_ROOT>" --force --json
```

**调度语义**：触发器 = 每周一 09:00（`New-ScheduledTaskTrigger -Weekly`），「每月一次」由 `monthly_audit.py` 的幂等守卫实现 —— JSONL 里最后一次 `status=ok` 的 `period` 与当前 `YYYY-MM` 相同即 skip。上一次 `failed` **不**阻断复验，`-Force` 强制重跑。不用「每月 1 日」触发器，是因为 PowerShell cmdlet 没有 `-Monthly`，且关机补跑（`StartWhenAvailable`）落到任意一天时日期守卫会误 skip。

**盘点项与阻断条件**：

| 项 | 判据来源 | 阻断条件 |
| --- | --- | --- |
| `verify_facts` | g20（`tools/facts/verify_facts.py --json`） | 非 0 退出或 `findings` 非空 |
| `docs_index` | D1–D17（`tools/gate/docs_index.py`） | 非 0 退出 |
| `repocheck` | 仓内自检口径（与 `scripts/run_all_gates.sh` 同参数） | 非 0 退出 |
| `portfolio` | FACT-08 表内自洽（140 行编号 / 分层求和 / 合计 / `137 = 140 − 3`） | 任一算术或编号不自洽 |

> **发布区目录数是观测项，不是判据**：`组合分级决策索引.md` 明写「工作区 repos 根按机器而异」（SIWPAN 实测 138、8RSV60V 实测 137）。拿一台机器的目录数硬判 137 会制造跨机假红，与 `verify_facts` 默认只判本机那份文件同一道理。实测值如实写进 JSONL 的 `deviations`，需要时加 `--strict-publish-area` 收紧为阻断。

**产物**：`tools/gate/audit/monthly-audit-runs.jsonl`（机器本地，`audit/*` 已被 `.gitignore` 覆盖；5MB 轮转同 `gate-runs.jsonl`），一行一次真跑，含 `period` / `host` / `commit` / 每项 `exit` 与 `ms` / `portfolio` 观测。文本日志按日落 `<ALLIN_LOG_DIR>\monthly-audit-<yyyy-MM-dd>.log`。**退出码 0 全绿或 skip，1 有阻断项，2 用法错，3 环境错** —— 非 0 由 `Get-ScheduledTaskInfo` 的 `LastTaskResult` 可见。

**编码纪律**：中文 Windows 上 `[Console]::OutputEncoding` 常为 gb2312（OEM 码页），PowerShell 会把 Python 的 UTF-8 stdout 解码成乱码 —— 2026-11-07 包装器首跑实测输出成 `SKIP锛?026-11...`。包装器在调用前临时切 UTF-8、拿到输出后立刻恢复；文本日志不用 `Tee-Object`（PS 5.1 默认 UTF-16LE 且无 `-Encoding`），改 `AppendAllText` 显式 UTF-8 无 BOM。**语法解析通过 ≠ 实跑可读**，跨语言子进程必须验编码。

**回归**：`scripts/run_all_gates.sh` 每次跑批会执行 `monthly_audit.py --selfcheck`（12 个夹具用例：表内自洽逐维破坏、发布区软/严判定、幂等守卫与坏行容错），真跑由任务⑤ 负责。

## 月度恢复演练调度（审查残留 #21，2026-11-08）

**为什么是仓内计划任务而不是 CI schedule**：本演练要真跑 `backup-allin.ps1` / `restore-allin.ps1` / robocopy，依赖本机 Windows 计划任务上下文与本地数据面；CI 侧没有这套 Windows 守护面，也不该把灾备演练绑到代码提交节奏。故沿用任务⑤ 的仓内调度范式（配方随仓 clone、注册动作由人在各机执行），**不新增任何 `.github/*` / `.workflow/*` 的 schedule**。

**调度语义**：`ALLIN-monthly-restore-drill` 触发器 = 每周一 10:00（`New-ScheduledTaskTrigger -Weekly`，没有 `-Monthly`；与任务⑤ 的周一 09:00 错开一小时，避免同刻并发的高 IO 与同目录留痕写入）。「每月一次」由 `restore-drill-task.ps1` 的幂等守卫实现 —— 读 `tools/gate/audit/restore-drill-runs.jsonl` 里最后一次 `status=ok` 的 `period`（`yyyy-MM`）与当前月相同即 SKIP；**skip 不写 JSONL**；上一次 `failed` **不**阻断复验；`-Force` 强制重跑；坏行（轮转残留 / 半行 / 畸形 JSON）跳过而不是让整份留痕失效；超 5MB 轮转为 `.1`（同 `gate-runs.jsonl` 口径）。

**包装器为什么用子进程**：`test_restore_drill.ps1` 内部用 `exit` 结束进程，包装器必须 `& powershell.exe -NoProfile -ExecutionPolicy Bypass -File <绝对路径>` 启动它再读 `$LASTEXITCODE`；若 `& <script>` 直接调用，`exit` 会连包装器一起终止，写不出留痕。

**四文件同目录约束**：`test_restore_drill.ps1` 顶部靠 `$PSScriptRoot` dot-source 同目录 `exclusion-policy.ps1`（共享排除策略单一真相源），`backup-allin.ps1` / `restore-allin.ps1` 也依赖它；**且 drill 以 `powershell.exe -File <同目录脚本>` 启这两个子进程，子进程 `$PSScriptRoot` 同样落在 deploy 目录** —— 即便将来去掉 dot-source，子进程路径也要求四文件（`test_restore_drill.ps1` / `backup-allin.ps1` / `restore-allin.ps1` / `exclusion-policy.ps1`）同在 `tools\deploy\`。包装器的环境检查逐个校验这四个文件，任一缺失即报「缺 `<文件名>`」并 exit 3；`register-tasks.ps1` 的部署物在位校验同样含 `exclusion-policy.ps1`，注册期就指名报错。这是**诊断纵深增强**（把失败从「运行期 exit 1」提前到「注册期 / 环境检查期就指名缺哪个文件」），链路本身已 fail-loud、不存在静默假绿。

**产物**：`tools/gate/audit/restore-drill-runs.jsonl`（机器本地，`/tools/gate/audit/*` 已被 `.gitignore` 覆盖），一行一次真跑，含 `ts` / `period` / `host` / `commit`（`git rev-parse --short HEAD`，取不到写 `unknown`）/ `exit` / `ms` / `status`（`ok` / `failed`）/ `forced`。文本日志按日落 `<ALLIN_LOG_DIR>\restore-drill-<yyyy-MM-dd>.log`（缺省 `<LOCALAPPDATA>\allin\logs`），含演练子进程完整输出。

**退出码**：`0` = 演练通过或 SKIP；`1` = 演练失败；`2` = 用法错（多余位置参数）；`3` = 环境错（缺 `test_restore_drill.ps1` / `backup-allin.ps1` / `restore-allin.ps1` / `exclusion-policy.ps1` 任一 / 缺 `powershell.exe` / 仓根找不到 / 日志目录不可创建 / 子进程启动失败）。非 0 由 `Get-ScheduledTaskInfo` 的 `LastTaskResult` 可见；包装器不写 `exit 0` 兜底、不吞 `$LASTEXITCODE`。

> **语义边界（不得包装成「灾备已验证」）**：这条自动化月度调度只证明「演练脚本逻辑按月回归」——`test_restore_drill.ps1` 的备份 / 恢复 / 备份排除 / 密钥通道独立断言按月被真跑过一遍、留痕可查、失败可见。它**不替代 P3 §4.1 的人工 SEV1 全链演练**：真实灾备切换、密钥唯一通道（website `backup-key` / `restore-key`）、异地恢复、以及真出事时按剧本人工接管，仍需人工按剧本执行并单独验收。

## 已知边界

- 计划任务为「登录/定时触发 + 当前用户」形态：不登录不运行（拍板：单用户本机交互式使用；NSSM 服务级自启仅备选不落地）。
- 守护语义边界：`RestartCount 5 / RestartInterval 1min` 只对**非零退出**触发；优雅退出（exit 0）不重启。
- 备份为同机异盘镜像，无异地副本（单人团队接受底线，P2-RD5）。
- 月度盘点的「每月一次」是**幂等守卫**而非触发器语义：一周最多唤醒 1 次，同月后续周次直接 skip 且不写 JSONL；`-Force` 与上次 `status=failed` 例外。
- 月度恢复演练同款幂等守卫，且**只覆盖演练脚本逻辑**：自动化跑通不等于真实灾备切换已验证（P3 §4.1 人工 SEV1 全链演练另算），见上一节语义边界。
- 演练依赖**四文件同目录**：`test_restore_drill.ps1` / `backup-allin.ps1` / `restore-allin.ps1` / `exclusion-policy.ps1` 必须同在 `tools\deploy\`（前三者 dot-source 最后一个；且 drill 启 backup/restore 子进程按同目录解析）；单独把 drill 拷到别处跑，会在其顶部 dot-source 失败即 exit 1，包装器环境检查则在更早阶段报「缺 `<文件名>`」并 exit 3。

## 许可

MIT-0 · 与 allin 主仓治理纪律一致（借鉴记账见 P3 文档 §7）。
