# DSH 分发版当前版本使用说明（0.1.7-rc.1）

> **编号** SPEC-104 ｜ **效力** 操作规范 ｜ **状态** 生效
> **生效** 2026-09-27 ｜ **最后修订** 2026-10-08 ｜ **适用面** siwpan/deepseek-harness 分发版的使用者与维护者
> **承载体** `g00`–`g18`（随分发版交付的 **18 条**治理门禁）；本文件是它们在 allin 侧的说明
> **引用格式** SPEC-104 §三

> **这是什么**：`siwpan/deepseek-harness`（**独立分发版**，上游 GitHub 官方仓仅作参考）的使用说明。
> 本文件是**在 allin 侧的存档副本**；DSH 仓内的中英配对版在 `docs/user/guide/distribution.md` 与 `distribution.zh.md`。
> **口径（2026-09-27 用户拍板）**：本分发版按自己的节奏演进，不再「对齐上游」；上游只用于形态比对。
> **同日落地**：治理规则已从「只在文档里」变成「随分发版交付的可执行门禁」，见下第三节。

---

## 一、这是什么 / 当前版本

| 项 | 事实 |
| --- | --- |
| 分发仓 | `gitee.com/siwpan/deepseek-harness`（本机检出 `/projects/deepseek-harness-master`） |
| 版本 | **0.1.7-rc.1**（钉在 `scripts/distribution-pin.json`） |
| 形态 | 源码 checkout + `tsx` 直跑（不是 npx 包）+ **外层自愈启动器** |
| 上游关系 | `github.com/deepseek-ai/deepseek-harness` **仅作参考**，绝不 fetch 进本分发版 |

## 二、启动与自愈

```powershell
python start-dsh-web.py              # 安装、构建、启动；需要时自愈修复 checkout
python start-dsh-web.py --check      # 体检：工具链、依赖、迁移、插件钉版
python start-dsh-web.py --diagnose   # 启动并把服务端输出全部落到日志文件
```

`finish-deploy.cmd` = 同样的活拆成四步手动跑（install → build → start → `--check`）。
**重建流程、升级纪律、镜像分层**见 DSH 仓的 `docs/DISTRIBUTION.md`（中文版 `DISTRIBUTION.zh.md`）。

## 三、治理机械保障（本次新落地，随分发版交付）

规则来源是**本仓**（`allin/docs/`，2026-09-27 前目录名为 `allin_push`），落地形态是 **DSH 仓内的 `governance/` 目录** —— 克隆即得，不依赖本机路径。

```powershell
pnpm run check:governance            # 全部 18 条门禁（2026-10-08 实测 18/18 clean）
pnpm run governance:selfcheck        # 证明每条门禁仍能抓到注入的缺陷（0 误报）
pnpm exec tsx governance/run.ts --list            # 列出 id / 档位 / 覆盖的规则
pnpm exec tsx governance/run.ts --only g01-paths  # 只跑其中几条
```

**退出码统一**：`0` 干净 · `1` 基线之外的新阻断 · `2` 用法错误 · `3` 环境错误。
**SKIP 不是通过**：跑不了的检查会打印 `SKIPPED (not a pass)` 并计数。

| 门禁 | 覆盖的规则 | 拦什么 |
| --- | --- | --- |
| `g00-meta` | 调试铁律 30 / 41 | 注册表/契约/自检不完整的门禁；治理目录里**没进索引**的 .py |
| `g01-paths` | 铁律 5、调试铁律 26 / 34 / 53 | 写死某台机器的绝对路径（**已泛化到 POSIX**，不是只看盘符） |
| `g03-credentials` | 铁律 0、敏感信息、调试铁律 52 | 索引内容里的凭据、`.git/config` 全文（含 `branch.*.remote`） |
| `g04-push-evidence` | 铁律 3、调试铁律 25 / 37 / 47 | 带凭据的远端 URL；分支分叉（同步状态只信 `git ls-remote`） |
| `g05-hygiene` | 铁律 0 / 4、调试铁律 54 | 产物/字节码/大文件入索引、`.gitignore` 缺凭据面、归档缺清单 |
| `g06-numbering` | 调试铁律 45 | 序号序列缺号；**中英配对列表形状漂移** |
| `g07-doc-freshness` | 调试铁律 57 / 58 | 自称环境事实源却没有时点；自称快照却没有失效条款 |
| `g08-deletion-evidence` | 治理准则·退役三查 | 删了文件却没有「功能面 × 接任者」对照表 |
| `g09-python-hygiene` | 调试铁律 35 / 38 / 43 | 文本 I/O 未显式编码、转义伪影、语法告警（存量 72 条已入基线） |
| `g10-failloud-probe` | OPS-E1 / E2 | 拿到坏输入却静默通过或静默失败的门禁 |
| `g11-undef-names` | 调试铁律 32 / 40 | 读了却从未定义的名字（`py_compile` 查不出的那类） |
| `g12-integrity` | 调试铁律 51 / 58 | 对象库不可读、`HEAD^{commit}` 解不出（盘自愈改坏 git 对象那一类） |
| `g13-docs-only` | OPS-D1 / G8 | `docs/` 下的脚本、归档、可执行位 |
| `g14-preset` | 铁律 5、调试铁律 42 | 治理 preset 与出厂件漂移、治理段里写了盘符 |
| `g15-docs-contract` | **`SPEC-005` 全部**、OPS-D6 / D7、调试铁律 45 | 文档枢纽索引契约（**选用制**）：文档没登记 / 索引指向不存在的文件 / 规范缺头部 / 规范名带日期或记录名无日期 / 分类错位 / ASCII 别名缺失 / 交接卷断号。本仓无 `docs/INDEX.md` 时记 `SKIPPED (not a pass)` |
| `g16-launcher-integrity` | 铁律 5、调试铁律 34 | 启动器把环境专属工具根**写死并带版本钉**（如 `versions/22.22.2-3`）→ 阻断；裸锚定可基线化但须写明理由；平台薄膜（SHIM_MATRIX）缺对 → 阻断。补 `g01` 看不到的「父目录在本机存在、工具一升级就静默退化」 |
| `g17-skip-visibility` | 调试铁律 39、OPS-E1 / E2 | 部署/启动脚本里被守卫包裹的验证调用**无 else、无输出**（`silent-skip`）或 Python `except` 吞掉验证失败（`swallowed-failure`）→ 阻断。是 `g10` 在部署侧的对应物；运维显式跳过的 flag 不算 |
| `g18-doc-bilingual-triad` | OPS-D9 | 文档**语言位与三方完备**：`missing-zh`（源文档无 `.zh.md` 对）/ `missing-record`（有对缺 `.i18n.yaml`）/ `source-not-english`（CJK 占比判出语言位调换）。与 `verify-translation-pairing` 分工：后者判「两侧是否一致」，本条只判「三方是否齐、各在其名所说的语言位」 |

**规则 → 门禁的逐条映射、引用契约、维护约定**在 DSH 仓的 `governance/RULES.md`（该目录已登记进 `translation-pairing` 排除表：它是中文主文档，不做双语配对）。

## 四、治理 preset 怎么装

```powershell
dsh plugin --profile web add <bundle 目录>          # 持久：patch 指向 governance/preset/allin.patch.yml
dsh web --patch governance/preset/allin.patch.yml   # 临时：单次启动的 overlay
```

装完重启 DSH，把 `agent-presets.default` 设为 `allin`（只影响新建会话）。回滚 = 卸 bundle 或把默认值改回 `cordis`（本 preset 用独立 id，工厂预设永远兜底）。
**校验**：`python governance/gates/g14_preset.py`；安装/校验/漂移响应的完整流程见 `governance/preset/README.md`。

## 五、当前版本已知问题

钉版、四类 SHAPE 漂移、单实例语义、回归清单都在 `docs/distribution-masterlist.md`（中文版 `.zh.md`）。
**本次新增**：`docs/DISTRIBUTION.md`、`docs/distribution-masterlist.md` 从「中文单语」补成**中英配对**（原本是 `verify-translation-pairing` 的两条存量红，现已转绿：全语料 1127 对全部一致）。

## 六、安装 / 校验 / 参考

- DSH 仓内配对版：[`docs/user/guide/distribution.md`](https://gitee.com/siwpan/deepseek-harness)（英文）+ `distribution.zh.md`（中文）。
- 参考：[Cordis 教程](https://deepseek-harness.github.io/deepseek-harness/develop/cordis-tutorial/)（底层插件框架怎么工作）、DSH 仓 `governance/README.md`（门禁怎么跑/扩展/重建基线）。
- 规则事实源仍在**本仓**：`docs/规范/SPEC-001-铁律.md`（铁律与准则）、`docs/规范/SPEC-004-调试铁律.md`（调试铁律 1–69）、`docs/规范/SPEC-105-治理模式建设指南.md`（复刻 playbook）。

---

*最后更新：2026-10-08（门禁口径订正 15 → **18 条**：补 `g16`–`g18` 三行，与 `governance/gates/` 及注册表实测一致；`check:governance` / `governance:selfcheck` 当日复跑均全绿）。本文件是 DSH 侧配对文档的中文同源副本，落点与命令按本仓习惯表述。*
