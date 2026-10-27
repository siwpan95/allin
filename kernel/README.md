# kernel —— allin 治理内核

allin 的「制度 + 文档枢纽 + 执行器」三合一治理体系中，**内核（kernel）** 是纯 Python + [Cordis](https://cordis.js.org/) 服务图（service-graph）的执行引擎。它不依赖 Node、不依赖网络，只把治理事实变成可调用的服务与可审计的挂载。

## 定位

- **不是** HTTP 服务：内核以 CLI / 库形式被调用（`python -m kernel ...` 或 `import kernel`）。对外 HTTP 接口由 `platform/apps/portal` 提供，见仓库根 `README.md` 的架构图与 `openapi/` 规范。
- **是** 治理事实的唯一权威来源：四套事实源（规范 / 事实源 / 记录 / 历史）通过内核服务对上层（agent、platform、门禁）统一暴露。

## 目录结构

| 文件 / 目录 | 作用 |
| --- | --- |
| `__init__.py` | 包入口；装配 Cordis 应用、暴露 `ctx` 服务面 |
| `registry.py` | `SERVICES` 白名单 —— 四大支柱（`docs` / `platform` / `preset` / `tools`）→ `kernel/services/*.py` 的映射，是「能挂什么服务」的代码边界 |
| `tree.py` | 通过 `cordis.allin.yml` 挂载子服务；entry-name 白名单即代码边界（未在 `cordis.allin.yml` 登记的入口一律不加载） |
| `paths.py` | 仓库内路径常量（根、规范目录、缓存目录等），全部相对仓根推导，**不写死任何机器盘符** |
| `_cordis_locate.py` | 定位托管 Cordis 运行时（先试已安装，再退回 `vendor/cordis`），与 `vendor/` 的回退策略一致 |
| `configs/` | 内核自身的配置片段（环境/阈值等） |
| `services/` | 四支柱的具体实现：`docs_service.py`（文档枢纽索引契约 D1–D8）、`platform_service.py`、`preset_service.py`、`tools_service.py` |

## 四大服务支柱

1. **docs（文档枢纽）** —— 维护 `docs/` 四分类（规范 / 事实源 / 记录 / 历史）的索引与契约，门禁 `docs_index.py` 即以其为判据。
2. **platform（集成平台）** —— 描述 `platform/` 子进程隔离聚合的契约。
3. **preset（治理预设）** —— 与 DSH `preset/allin/allin.patch.yml` 的 `GOVERNANCE:BEGIN/END` 段同源，是治理事实的可执行载体。
4. **tools（执行器）** —— 聚合 `tools/` 下门禁与工具的调用契约。

## 设计约束（铁律）

- **路径零硬编码**：任何机器相关绝对路径（Windows 盘符 / POSIX `/Users` 等）一律不得写入源码；门禁 `g01_paths` 专门扫描并阻断（详见 `tools/gate/governance/gates/g01_paths.py`）。
- **入口白名单**：未在 `registry.py` / `cordis.allin.yml` 登记的入口不得加载。
- **可审计**：内核所有变更须过治理门禁（`bash scripts/run_all_gates.sh`）。

## 用法 / 示例（本地运行）

```bash
# 仅跑内核相关的治理门禁
bash scripts/run_all_gates.sh

# 直接调用文档枢纽索引契约（等价于门禁 docs_index）
python tools/gate/docs_index.py

# 示例：以库形式使用四支柱服务
from kernel import make_app          # 装配 Cordis 应用
app = make_app()                     # 返回 ctx 服务面
docs = app.ctx.docs_service         # 取文档枢纽服务
```

## 许可

本目录与整个仓库同受根目录 `LICENSE`（MIT No Attribution，简称 MIT-0）管辖；
内核不引入额外许可义务。`kernel/LICENSE` 为本目录的同源副本，便于组件级分发。
