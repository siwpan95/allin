# `governance/preset/` — 治理 persona 的可重装载体

> **这是什么**：把「分发版工作纪律」做成一个可安装的 DSH agent preset（`allin`）。装进 profile 后，新会话的第一条消息就带治理段；没装或挂载失败时会话自动降级到工厂 `cordis`/`standard`，不会崩。
> **口径**：本仓是 `siwpan/deepseek-harness` **独立分发版**；本 preset 是分发版自有资产，与上游 GitHub 官方仓无关。

## 一、`allin.patch.yml` 是什么（恒等式，可复核）

它 = **出厂 `cordis` preset 的逐行副本** + 三处差异：

| 差异 | 值 | 为什么 |
| --- | --- | --- |
| 顶层 id | `preset-allin` | 避免覆盖同名的出厂行 |
| preset `id` | `allin`（不是 `cordis`） | 同名 id 由靠前根赢；叫 `cordis` 会被随包那份压住永不生效 |
| `order` | `5`（出厂是 `4`） | 保证本行胜出 |
| persona `prefix` | 末尾追加 `<!-- GOVERNANCE:BEGIN -->…<!-- GOVERNANCE:END -->` 治理段 | 这就是治理本身 |

**恒等式可复跑**：删掉治理段，本文件应逐行等于 `packages/bundle/web-app/presets/cordis.patch.yml`（除 id 与 order）。
**机械校验**：`python governance/gates/g14_preset.py` —— 标记成对且有序、治理段内**无盘符路径**、插件名序列与出厂件**逐项相等**、断言的仓内文件存在、提到的门禁 id 都已登记。

## 二、安装（三选一，推荐 1）

```powershell
# 1) 声明式 bundle（持久，推荐）：包一个 npm 包，patch 指向本文件
#    package.json 里写 { "dsh": { "bundle": { "patch": "cordis.patch.yml" } } }
dsh plugin --profile web add <bundle 目录>

# 2) 启动 overlay（临时，零安装）
dsh web --patch governance/preset/allin.patch.yml

# 3) 直接追加进 profile 用户层
#    %USERPROFILE%\.dsh\profiles\web\cordis.patch.yml
```

装完**重启 DSH**，在设置 → Agent presets 里确认出现 `allin` 卡片，并把它设为默认（`agent-presets.default: allin`）。**只影响之后新建的会话**。

> **⚠ 源目录改名或搬动后必须重跑一次 `add`**：`link:` 装法是把 profile 的 `node_modules/<name>` 指向源目录，
> 源目录一改名，这条链接就悬空 —— 插件管理器会直接解不开（`plugin list` 抛 `cannot resolve profile bundle`），
> **重启后新会话静默失去治理段**（降级到工厂预设，不崩但没治理段）。同机实测过一次（`allin_push` → `allin`）。
> 机械兜底：`g14-preset` 的 profile 探针会当场报 `bundle-unresolved`。

## 三、校验与回滚

```powershell
python tools/gate/governance/gates/g14_preset.py     # 结构层：标记/路径/插件序列/引用 + profile 探针
python tools/gate/governance/gates/g14_preset.py --selfcheck   # 证明这条门禁真的会红（9 抓 / 2 静默 / 0 误报）
python tools/gate/governance/gates/g14_preset.py --no-profile  # 只看仓内结构，不读仓外 profile
python tools/gate/governance/gates/g14_preset.py --profile <DSH profile 目录>   # 指定别的 profile（CI/多 profile）
```

> **聚合入口默认不读仓外**：`pnpm run check:governance` 带 `--no-profile`（只转发给声明 `profileProbe`
> 的门禁，即本门禁），因此在 CI 或别人的机器上不会因为「没有 profile」而误报或假绿 —— 那种情况下
> 探针记 SKIP 并计数。**搬运/改名仓目录之后要查部署面**，请单跑上面第一条，或
> `pnpm exec tsx governance/run.ts --only g14-preset`。

profile 探针读 `$DSH_HOME/profiles/web/package.json`（未设 `DSH_HOME` 时取用户目录下 `.dsh`）：
本地 `link:`/`file:` bundle 的**链接目标必须存在**、`node_modules/<name>` 必须可解析、bundle 声明的
`dsh.bundle.patch` 必须存在且 `GOVERNANCE:BEGIN/END` 成对；官方 `@deepseek-ai/*` 从 DSH 安装目录解析，
只计数豁免；profile 不存在记 **SKIP（不是通过）**。

- **回滚**：把 `agent-presets.default` 改回 `cordis`，或卸掉 bundle / 删掉追加的 insert 行 —— 因为 id 独立，工厂预设永远兜底。
- **挂载失败怎么发现**：`dsh --dump-config` 是免启动合成，**不挂载 preset**；真正确认要新建一个会话，看治理段在不在。

## 四、上游破坏性变更的响应（漂移了怎么办）

DSH 是 pre-release 快照，上游可能重命名/移除插件。症状：新会话绑不上 `allin`，或 `g14-preset` 报 `capability-drift`。

1. 跑 `python governance/gates/g14_preset.py` 看差异条目数；
2. 用 `tmp/build-preset.py` 同款做法**从当前出厂件重新生成**：复制出厂声明 → 改 id/order → 把治理段（本仓 `allin.patch.yml` 内 BEGIN/END 之间那段，逐字保留）追加到 persona prefix；
3. 重跑 `g14-preset` 与 `pnpm run check:governance`，两条都绿才算回放完成；
4. 治理段文本本身只改 `governance/RULES.md` + 本目录，别在 preset 里即兴加规则（规则要有对应门禁）。
