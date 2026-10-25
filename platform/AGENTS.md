# AGENTS.md — allin-platform 常备上下文

> 面向 AI agent 与新协作者：每次会话都该在场的事实只放本文件；其余一律链接归属文档。
> 文档税表（一个事实一个家）见 [docs/architecture.md](docs/architecture.md)。

## 常备命令

```bash
npm install --registry=https://registry.npmmirror.com   # 安装依赖（唯一三方依赖 js-yaml）
npm run check          # 注册表审计（exit 0 = 全通过；异机加 PLATFORM_PATH_CHECK=absolute）
npm test               # 内核 + 前台 + CLI 测试（node --test）
npm run harness        # 离线黄金值门禁（exit 0 = 全绿）
npm run portal         # 手动启动门户（PORT 自选，缺省 9000 仅调试用）
node apps/cli/src/index.js list   # CLI（allin list/search/status/start/stop/...）
```

推荐入口：双击 `start-platform.bat`（PORT=0 临时端口 + 自动开浏览器，关窗即释放端口）。

## 环境变量（唯一登记处）

| 变量 | 语义 | 缺省 |
|---|---|---|
| `PLATFORM_ROOT` | 运行时状态根（data/） | 仓库根 |
| `PLATFORM_PORTS` | 外部端口分配表（唯一事实源） | 仓内 `registry/ports.yaml`（重建默认） |
| `PLATFORM_REGISTRY` | registry/projects 目录 | 仓内 `registry/projects` |
| `PLATFORM_PATH_CHECK` | `exists`（默认，本机 fail-loud）/ `absolute`（异机/CI 仅校验形状） | `exists` |
| `PLATFORM_ALLIN_ENGINE_CWD` | an-engine 引擎项目目录（引擎页） | 未配置 → 引擎页报「未配置」 |
| `PLATFORM_PYTHON` | 引擎 CLI 用的 python | `python`（PATH） |

## 纪律速览

1. **聚合不融合**：平台零业务代码，项目独立进程（子进程隔离），绝不 import 项目代码。
2. **端口纪律**：新端口先查 `PLATFORM_PORTS`（外部端口分配表），未登记拒绝登记。
3. **一切注册可逆**：launch 必可停，每次启停写 tasks.log（日志即事实源，超 5MB 轮转）。
4. **fail-loud**：误配加载即炸；引用缺失不静默跳过（gitee 故障显式上告警，不伪装成无更新）。
5. **状态文件原子写**：running.json / workshop.json / portal.port 一律 temp+fsync+rename（+.bak 回退）；日志归档前 fsync（durable 语义，2026-09-24 Phase 1）。
6. **Host 围栏**：门户只接受回环 Host（127.0.0.1 / localhost / [::1]），防 DNS rebinding；GET 读取面同样受保护（2026-09-24 Phase 1）。

详细架构与决策记录：[docs/architecture.md](docs/architecture.md)、[docs/decisions/](docs/decisions/)。
