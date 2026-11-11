# allin-platform 门户常驻部署

> **补哪个缺口**：`docs/新人开发上手指南.md` 附录 A 第 6 项「平台门户常驻部署方式」。
> **性质**：部署说明 + **一次本机验证性部署记录**（§6）。
> **边界（先说清，免得被当成上线报告）**：本仓**不代宿主配置常驻** —— 计划任务 / systemd / 服务包装属于宿主侧动作，本文只给可直接复制的步骤。§6 记录的是本机起停验证，**不是生产常驻上线**。

---

## 0. 先认清形态：默认按需，不是常驻

- 门户是零依赖纯 Node http 的独立网页应用，`server.listen(port, '127.0.0.1')` —— **只监听回环**，外部访问必须自行反代 + 鉴权。
- `PORT` 未设时默认 **0**（OS 分配临时端口）；`PORT=9000` 可手动占固定端口，但 `9000` 在 `docs/事实源/ports.yaml` 已登记为**退役**，只作「手动可选」，不新增固定端口占用。
- 因此「常驻」= **宿主负责进程守护**，仓库只负责三件事：写端口发现文件、提供健康检查、退出时清理。
- 每次重启端口可能变 ⇒ **消费方一律读 `data/portal.port`，不要硬编码端口**。

## 1. 运行前提

| 项 | 要求 | 说明 |
| --- | --- | --- |
| Node.js | `>=22`（`platform/package.json` 的 `engines`） | 用了 `AbortSignal.timeout`、原生 `fetch` 等 |
| 依赖 | `platform/node_modules/@allin/core` 存在 | 缺则 `npm install --no-audit --no-fund`（workspaces） |
| 数据目录 | `platform/data/`（已 gitignore） | 放 `portal.port` / `portal.token` / `tasks.log` / `running.json` |
| 令牌 | `data/portal.token`（服务启动随机生成，0600）或 `ALLIN_PORTAL_TOKEN` 注入 | 所有**状态变更**接口需 `X-Allin-Token` 头；只接回环也不放行 |
| 权限 | 只需对 `platform/data/` 可写 | 不需要管理员/root 跑服务本身；注册计划任务/systemd 才需要 |

## 2. 启动方式

### 2.1 交互式（默认，非常驻）

```bash
cd <PATH>/platform
PORT=0 npm run portal          # 等价于 npm start --workspace @allin/portal
```

Windows 也可双击 `start-platform.bat`：它自动装依赖、`set PORT=0`、`PORTAL_AUTO_OPEN=1` 并开浏览器。
⚠ **常驻不要用这个 bat** —— 它带 `pause`、会自动开浏览器，且窗口关闭才算退出。

### 2.2 Windows 常驻（计划任务，需管理员注册一次）

直接起 Node（不设 `PORT` 即默认 0，无需环境变量）：

```powershell
$dir  = '<PATH>\platform'
$node = (Get-Command node).Source
$act  = New-ScheduledTaskAction -Execute $node `
          -Argument 'apps/portal/src/index.js' -WorkingDirectory $dir
$trg  = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName 'allin-portal' -Action $act -Trigger $trg `
          -Description 'allin-platform portal (loopback only)'
Start-ScheduledTask -TaskName 'allin-portal'
```

- 查看：`Get-ScheduledTask -TaskName 'allin-portal' | Get-ScheduledTaskInfo`
- 停止：`Stop-ScheduledTask -TaskName 'allin-portal'`（正常终止会清理 `portal.port`）
- 需要固定端口给反代时，把 `-Argument` 换成经 `cmd /c "set PORT=9000 && node apps/portal/src/index.js"` 的包装；注意 `9000` 是手动可选口径。
- `nssm` / `pm2-windows-service` 同理：`ExecStart` 指向 `node apps/portal/src/index.js`，工作目录设为 `platform/`。

### 2.3 Linux / macOS 常驻（systemd unit 示例）

```ini
[Unit]
Description=allin-platform portal
After=network.target

[Service]
Type=simple
User=allin
WorkingDirectory=<PATH>/platform
# 不设 PORT 即默认 0（临时端口）；需要固定端口才放开下一行
# Environment=PORT=9000
EnvironmentFile=-/etc/allin/portal.env      # 可选：ALLIN_PORTAL_TOKEN 等，文件不入库
ExecStart=/usr/bin/node apps/portal/src/index.js
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now allin-portal
systemctl status allin-portal
```

`systemctl stop` 发 SIGTERM ⇒ 门户显式收尾并清理 `portal.port`；`Restart=always` 重启后端口可能变化，靠端口发现文件重新找。

> pm2 / supervisor / 容器编排均可套同一形态：**工作目录 = `platform/`、入口 = `apps/portal/src/index.js`、守护进程崩溃自动拉起**。本仓未提供容器镜像，容器化需自行补 Dockerfile 与数据卷。

## 3. 端口发现与健康检查

**发现优先级**（`platform/harness/harness.mjs` 的 `probeTarget`）：

1. 环境变量 `PLATFORM_PORTAL_URL`（显式覆盖）
2. `platform/data/portal.port`（门户 listen 成功后原子写入的实际端口）
3. manifest 的 `target`（`http://127.0.0.1:9000/`，仅兜底）

| 检查 | 命令 / 端点 | 期望 |
| --- | --- | --- |
| 首页 | `GET /` | `200` 且响应含 marker `allin-platform` |
| 状态 | `GET /api/status` | `200`，`boundPort` = `portal.port` 的值 |
| 编排黄金值 | `cd platform && npm run harness` | `OVERALL: ALL GOLDEN VALUES MATCH`，exit 0 |

`harness` 的 `portal-health` 是 **informational 三态**（S2，契约见 `harness/spec.md`）：

| 情况 | 输出 | 判定 |
| --- | --- | --- |
| 无 HTTP 响应（没起 / 端口无监听） | `portal-probe="OFFLINE"` | **不判失败**，exit 0 |
| 有响应且 200 + marker | `portal-probe=200` | 通过，exit 0 |
| 有响应但非 200 / marker 缺失 | `ERR(status …)` / `ERR(marker missing…)` | **计失败**，exit 1 |

⇒ **常驻部署的验收看 `portal-probe=200`，不是「harness 不红」** —— 门户没起时 harness 本来就绿。

## 4. 退出与清理（S3）

| 退出方式 | 是否清理 `portal.port` |
| --- | --- |
| Ctrl+C / SIGINT、SIGTERM、`systemctl stop` | ✅ 信号 handler 显式清理后退出 |
| `process.exit` / `/api/shutdown` / 事件循环自然结束 | ✅ `exit` handler 清理 |
| `taskkill /F`、`kill -9`、断电 | ❌ 拦不住，但**下次启动会先清掉陈旧文件再写自己的端口** |

常驻服务重启前，若 `portal.port` 存在，以 `GET /api/status` 探活确认它属于活进程；不要拿文件内容当存活依据。

## 5. 排障

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `harness` 显示 `OFFLINE` | 门户没起，或 `portal.port` 是陈旧端口、无进程监听 | 起门户后重跑；`OFFLINE` 本身不是故障 |
| `portal-health` FAIL | 反代改写了首页 / 指向了别的服务 / 返回非 200 | 用 `curl -i http://127.0.0.1:<port>/` 直连确认 marker |
| `portal.port` 残留旧端口 | 上次强杀 | 无需手工删，下次启动自动清；或删文件后重启 |
| 写接口 401 / 令牌失效 | 令牌文件被重建、多实例各自写同一文件 | 统一用 `ALLIN_PORTAL_TOKEN` 注入，只跑一个实例 |
| 装依赖失败 | 镜像代理不可用 / 网络 | `start-platform.bat` 已改为「镜像可选、失败回退公网」；或手动 `npm install` |
| 外部访问不通 | 只监听 `127.0.0.1` | 反代 + TLS + 鉴权，本仓不提供，也不要直接改成 `0.0.0.0` |
| 多实例抢端口文件 | 当前是「单实例 + 单点发现」语义 | 只跑一个门户实例；多实例需另设 `PLATFORM_ROOT` 隔离 |

## 6. 一次实际部署记录（2026-11-11，本机验证性）

| 项 | 实测 |
| --- | --- |
| 时点 / 机器 | 2026-11-11，`@SIWPAN`（Windows） |
| 启动 | `node apps/portal/src/index.js`（默认 `PORT=0`），输出 `[allin-platform portal] http://127.0.0.1:6501/` |
| 端口发现 | `data/portal.port` = `6501`，与 `/api/status` 的 `boundPort` 一致 |
| 首页 | `GET /` ⇒ `200`，marker `allin-platform` = `true` |
| 状态 | `GET /api/status` ⇒ `{"version":"0.1.0","uptime":1,"platform":"allin-platform","boundPort":6501}` |
| 编排验收 | `npm run harness` ⇒ exit **0**；`[PASS] portal-health … portal-probe=200/4ms`；`OVERALL: ALL GOLDEN VALUES MATCH` |
| 优雅退出 | 触发 SIGINT 收尾 ⇒ 进程 exit 0，`data/portal.port` **已清理（不存在）**；顺带消除了此前残留的陈旧端口 `4373` |

**结论与边界**：以上证明「启动 → 端口发现 → 在线探活 → harness 在线验收 → 退出清理」这条链路在本机真实跑通，**不是生产常驻上线记录**。生产常驻仍需在宿主侧按 §2.2 / §2.3 注册守护，并留一次真实常驻时长的运行记录（本仓不代做）。

## 7. 本文未覆盖

- 容器镜像 / Dockerfile / 编排清单；
- HTTPS 终止、反向代理、外网暴露与 Web 应用防火墙；
- 日志集中收集（`tasks.log` 只有仓内轮转，5MB 归档一代）；
- 多实例高可用（当前是单实例 + 单点端口发现）。

---

*本文随 2026-11-11 附录 A 第 6 项补齐落地；S2/S3 的行为改动以 `harness/spec.md` 与 `apps/portal/src/index.js` 的实现为准。*
