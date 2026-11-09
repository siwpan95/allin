# allin × NetBox 部署说明（骨架已落仓于 `deploy/netbox/`）

> 定位：**资产与关系的派生视图**。Git 内的结构化真身是唯一写入权威，NetBox 只读消费、绝不反向写回。
> **P0-1 推进状态（2026-11-09）**：数据侧与逻辑侧已就绪——`facts/facts.json` 含 3 台 public 机器，`sync_from_git.py --selftest` PASS、dry-run 精确产出 3 设备 + 13 服务；`docker-compose.override.yml` 与 `.env.example` 已配齐。**唯一阻断项是 NetBox 服务本身未安装**（Docker Desktop / WSL2 未装），待管理员授权安装后 `--apply` 即达成「3 机可见」。
> 依据：NetBox v4.7.4（2026-10-27）/ Apache-2.0 核心；`netbox-community/netbox-docker` release 分支。
> 官方 wiki 明确 Windows 原生不在支持范围，需 Docker Desktop（WSL2 Linux backend）或 WSL2 内运行：
> <https://github.com/netbox-community/netbox-docker/wiki/Getting-Started>

## 1. 本机前置（2026-11-09 实测）

| 项 | 实测 | 动作 |
|---|---|---|
| `docker` | **NOT FOUND** | 装 Docker Desktop 并启用 WSL2 集成 |
| `wsl` | `/c/WINDOWS/system32/wsl` 存在 | `wsl --install -d Ubuntu-24.04`（若发行版未装） |
| 磁盘 | C 119G/剩 37G(70%)、D 406G/剩 321G、E 407G/剩 389G | 数据卷与镜像放 **E:**（不要占 C）；在 Docker Desktop 改 disk image location |
| 端口 8000/5432/6379 | 均空闲 | NetBox 只绑 `127.0.0.1:8000` |
| Python / Node | 3.13.14 / v22.22.2 | 同步脚本用 `E:\Python314\python.exe` |
| F 盘 | 实测 232G / 剩 154G，与用户级记忆「F=14.32GB U 盘」**不一致** | ⚠ 落盘前现场确认介质与可移动性，别把数据库放上去 |

> ⚠ NetBox 4.7 把最低要求抬到 **PostgreSQL 15+ / Redis 6.0+**，且 `django-mptt → ltree` 迁移
> 会阻塞读写数分钟、实际不可逆（官方 <https://netboxlabs.com/blog/netbox-4-7-is-ga>）。
> 首次上线直接锁 4.7.x，别从 4.6 原地升；`pip install netbox` 在 4.7 是实验性、**不建议生产**。

## 2. 许可红线（必须先拍板）

| 组件 | 许可 | 与 MIT-0 公开仓的关系 |
|---|---|---|
| NetBox 核心 | **Apache-2.0** | 可自由自用；仓内只放配置片段，不放代码 |
| `netbox-docker` | Apache-2.0 | 同上 |
| `netbox-mcp-server` | Apache-2.0 | 同上 |
| **`netbox-branching`**（4.x 变更分支） | **NetBox Limited Use License 1.0**（source-available，非 Apache） | ⚠ 不等于开源；若要求全链路 MIT/Apache，需接受该组件为例外或改用 Dolt 分支 |
| **Custom Objects 插件**（全域自定义实体） | 同上，非 Apache | ⚠ 同上；不用它则「机器-卷-运行时-仓库」只能塞 custom fields（有硬限制） |

## 3. 官方 compose 形态（不要自己发明）

`release` 分支 `docker-compose.yml` 起 **5 个服务**：`netbox`（web）、`netbox-worker`（RQ）、
`postgres`（18-alpine）、`redis`（任务队列）、`redis-cache`（缓存）；另有 `netbox-housekeeping`
profile（懒加载）。镜像 tag 形如 `docker.io/netboxcommunity/netbox:v4.7-5.1.1`，
`VERSION` 与 `NETBOX_DOCKER_PROJECT_VERSION` 由 `.env` 决定，**不能用 `latest`**。
官方 `netbox` 服务默认不发布端口，必须靠 `docker-compose.override.yml` 补 `ports`。

## 3.5 安装前置（需管理员授权，当前本机未装）

> 以下动作涉及系统级安装、可能重启、大体积下载（Docker Desktop ~1GB+，默认落 C 盘而 C 盘快满），
> 属 **需放行的重环境变更**，不在沙箱非交互会话内执行；由全哥在**管理员 PowerShell / 终端**里逐项跑。
> 本骨架已把这些动作隔离成清单，跑完再回 §4 即可。

```powershell
# ① 装 WSL2 + Ubuntu 24.04（若 wsl --list 为空）
#   需管理员；可能要求重启一次
wsl --install -d Ubuntu-24.04
wsl --list --verbose          # 确认 VERSION=2、STATE=Running

# ② 装 Docker Desktop（Windows，WSL2 backend）
#   需管理员；装完进 Settings → Resources → WSL Integration 勾选 Ubuntu-24.04
winget install -e --id Docker.DockerDesktop
# 装完后把镜像/数据盘位置改到 E:（不要占 C）：
#   Settings → Resources → Advanced → Disk image location = E:\Docker
#   再把默认 WSL distro 里 /opt 放到 E: 或挂 E: 卷

# ③ 验证 Docker 守护进程在线（在 Git Bash / PowerShell 均可）
docker version
docker compose version       # 需 v2（随 Docker Desktop 自带）
```

> ⚠ C 盘告警：本机 C 剩约 37G（70% 用）。Docker Desktop 默认镜像盘在 C，必须改到 **E:**，
> 否则首次 `docker compose pull` 拉 NetBox 镜像会撑爆 C 盘（§1 实测）。
> ⚠ F 盘介质可移动性未现场确认（§1 备注），**数据库 / 镜像不要放 F:**。

## 4. 最小部署步骤

```bash
# 在 WSL2 的 Ubuntu 里（不是 Git Bash）
git clone -b release https://github.com/netbox-community/netbox-docker.git /opt/netbox-docker
cd /opt/netbox-docker
# 覆盖文件来自本仓 deploy/netbox/（已落仓，不再走 blueprint/deploy）
cp /mnt/e/projects/allin/deploy/netbox/docker-compose.override.yml ./docker-compose.override.yml

# 密钥一律从仓外注入（公开仓铁律 0 / g03-credentials），例如：
export NETBOX_SECRET_KEY="$(openssl rand -base64 50 | tr -d '\n')"
export NETBOX_DB_PASSWORD="$(openssl rand -hex 24)"
export NETBOX_REDIS_PASSWORD="$(openssl rand -hex 24)"
export NETBOX_SUPERUSER_PASSWORD="$(openssl rand -hex 24)"
export NETBOX_SUPERUSER_API_TOKEN="$(openssl rand -hex 24)"
export NETBOX_API_TOKEN_PEPPER_1="$(openssl rand -hex 32)"

docker compose pull && docker compose up -d
docker compose logs -f netbox          # 首次 migration 数分钟
curl -sS http://127.0.0.1:8000/api/ -H "Authorization: Bearer nbt_..." | head
```

> v2 token 形如 `Bearer nbt_<key>.<token>`；legacy `Token <t>` 自 4.6 弃用、**5.0 移除**。
> `API_TOKEN_PEPPER_1` 一旦变更，所有 v2 token 失效 ⇒ 必须随 `configuration/` 目录一起备份。
> 官方 REST API 文档：<https://netboxlabs.com/docs/netbox/en/stable/integrations/rest-api/>

## 5. 写路径：Git → NetBox（单向）

`sync_from_git.py` 是本骨架提供的幂等导入器：

```bash
E:/Python314/python.exe deploy/netbox/sync_from_git.py --selftest      # 幂等自检
E:/Python314/python.exe deploy/netbox/sync_from_git.py                 # dry-run（默认）
NETBOX_URL=http://127.0.0.1:8000 NETBOX_TOKEN=nbt_... \
  E:/Python314/python.exe deploy/netbox/sync_from_git.py --apply        # 显式确认才写
```

- 映射：`machines → /api/dcim/devices/`（custom fields 带 `allin_observed_at` / `allin_evidence_ref`）、
  `ports → /api/ipam/services/`；
- 用本地 `netbox_state.json` 的 payload 摘要做幂等（**不入库、可重建**）；
- **默认 dry-run**，对齐 ADR-0003「默认只读、写入必须显式确认」；
- ⚠ 官方内置 **Data Sources** 只能同步 Config contexts / Config Templates / Export Templates，
  **不能创建 Device / Service** ⇒ 自定义 REST 同步是必需项，不是偷懒；
- ⚠ `pynetbox` 若不带 `strict_filters=True`，未知过滤参数会被**静默忽略并返回全表**
  （官方 <https://netboxlabs.com/docs/netbox/en/stable/integrations/python-library/>）；
  本骨架用标准库 urllib 规避该坑，但仍须给每个 API 调用显式断言返回条数。

## 6. 防循环、防泄漏、防 SPOF

| 风险 | 对策 |
|---|---|
| Event Rule → webhook → 同步脚本 → 再次触发 Event Rule | 给同步用独立 service account，Event Rule 条件里排除该 user；payload 带 `X-Allin-Sync: 1` 头，收到即跳过 |
| 资产信息泄漏进公开仓 | schema `visibility` 字段分级；`sync_from_git.py` 只同步 `public`；API token 只读且限定来源 IP；`ISOLATED_DEPLOYMENT=true` 禁外联 |
| 单机 SPOF | Postgres 每日 `pg_dump` + media 卷快照到 E:；**`docker compose down -v` 会删光数据**，写进运维禁令 |
| NetBox 里被人工改坏 | NetBox 表达 **desired state**，不是 operational state；所有对象 comments 标注「由 Git 单向生成，勿编辑」，定期跑 parity 对账 |
| 跨机访问 | 不开防火墙入站，走 SSH 隧道；对齐 portal 的 loopbackOnly 纪律（SPEC-204 §4） |

## 7. 最小验收（可复现）

1. `curl http://127.0.0.1:8000/api/dcim/devices/` 带 Bearer token 返回 3 台机器；
2. `sync_from_git.py` 连续跑两次 `--dry-run`，第二次 `create=0 / update=0 / unchanged=N`；
3. 改 Git 真身一个字段 → dry-run 出现 `update=[dcim.devices/SIWPAN]`；
4. `--apply` 后 NetBox changelog 出现对应记录，且 Git 侧 `git status` 无变化（证明单向）；
5. 停掉整个 NetBox 栈，跑 `scripts/run_all_gates.sh` 必须仍 **20/20 全绿**（离线治理面不受影响）。

## 8. 官方 / 一手来源

- 版本与升级：<https://netboxlabs.com/blog/netbox-4-7-is-ga>
- 安装与 compose：<https://github.com/netbox-community/netbox-docker/wiki/Getting-Started>
- 5.0.0 移除默认密钥：<https://newreleases.io/project/github/netbox-community/netbox-docker/release/5.0.0>
- Custom Fields 模型：<https://netboxlabs.com/docs/v4.4/netbox/models/extras/customfield>
- Custom Objects（非 Apache 插件）：<https://netboxlabs.com/docs/extensions/custom-objects/>
- REST API / token：<https://netboxlabs.com/docs/netbox/en/stable/integrations/rest-api/>
- NetBox MCP server（只读，Apache-2.0）：<https://netboxlabs.com/blog/new-ways-use-ai-netbox-open-sourced> · <https://github.com/netboxlabs/netbox-mcp-server>
- Branching（非 Apache 插件）：<https://github.com/netboxlabs/netbox-branching>
