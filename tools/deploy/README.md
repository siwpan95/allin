# tools/deploy —— allin 部署运维物（Windows 计划任务 + 每日备份）

> 依据：P3 部署实施方案（team 工作区）· 拍板口径 2026-11-04（4 任务 + 备份根异盘）。
> 纪律：本目录内脚本**零盘符字面量**（g01 门禁）——真实路径一律 env（`ALLIN_ROOT` / `ALLIN_BACKUP_ROOT` / `ALLIN_LOG_DIR`）或注册期实参注入；`.ps1` 全部 UTF-8 BOM（check_ps1_bom 门禁）。

## 文件清单

| 文件 | 职责 |
|---|---|
| `backup-allin.ps1` | 每日备份：website 库 wal_checkpoint(TRUNCATE) → robocopy /MIR platform/data 与 website/data（排除 keys 与种子口令文件）→ manifest.json（逐文件 sha256 + robocopy 退出码 <8 判定）→ 按目录名 7 天轮转 → 运行日志 14 天清理 |
| `start-website-task.ps1` | 计划任务包装器：登录拉起 website 常驻（9042），按日重定向日志，Node ≥22.5 前置校验，退出码透传 |
| `start-portal-task.ps1` | 计划任务包装器：登录拉起 portal 常驻（PORT=0 临时端口 + data/portal.port 文件发现，零新增常驻端口） |
| `register-tasks.ps1` | 注册 4 个 ALLIN-* 计划任务（website / portal / daily-backup / weekly-e2e）；`-Unregister` 一键回滚 |

## 安装（一次性，全部免管理员）

```powershell
# 1) 用户级 env（对新开进程生效；<REPO_ROOT> / <BACKUP_ROOT> 按本机实际填写，
#    盘符只出现在本机命令与任务计划参数中，不进仓内任何文件）
setx ALLIN_ROOT        "<REPO_ROOT>"
setx ALLIN_BACKUP_ROOT "<BACKUP_ROOT>"        # 备份根必须与数据所在盘异盘（同机异盘底线）
setx ALLIN_LOG_DIR     "<LOG_DIR>"            # 可省；缺省 <LOCALAPPDATA>\allin\logs

# 2) 确认部署物在位后注册 4 个计划任务（在 powershell 中运行）
powershell -NoProfile -ExecutionPolicy Bypass -File "<REPO_ROOT>\tools\deploy\register-tasks.ps1"
```

注册完成后验证：

```powershell
Get-ScheduledTask -TaskName "ALLIN-*" | Format-Table TaskName,State
Get-ScheduledTaskInfo -TaskName ALLIN-website-autostart,ALLIN-portal-autostart,ALLIN-daily-backup,ALLIN-weekly-e2e |
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
Stop-ScheduledTask   -TaskName ALLIN-website-autostart     # 停常驻（恢复演练等场景）
powershell -NoProfile -ExecutionPolicy Bypass -File "<REPO_ROOT>\tools\deploy\register-tasks.ps1" -Unregister
```

**监控最小化三件套**（P3 §6）：① `Get-ScheduledTaskInfo`（上方命令）② 探活 `curl http://127.0.0.1:9042/healthz` + 读 `platform/data/portal.port` 探 portal + `python allin_cli.py status` ③ 周度 `ALLIN-weekly-e2e` 自动跑 `npm run smoke:e2e`。

## 已知边界

- 计划任务为「登录/定时触发 + 当前用户」形态：不登录不运行（拍板：单用户本机交互式使用；NSSM 服务级自启仅备选不落地）。
- 守护语义边界：`RestartCount 5 / RestartInterval 1min` 只对**非零退出**触发；优雅退出（exit 0）不重启。
- 备份为同机异盘镜像，无异地副本（单人团队接受底线，P2-RD5）。

## 许可

MIT-0 · 与 allin 主仓治理纪律一致（借鉴记账见 P3 文档 §7）。
