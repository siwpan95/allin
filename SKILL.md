---
name: repocheck
description: Maintain the repocheck repo health tool (本 SKILL.md 所在仓库根). Self-contained offline scanner with 30 health checks, severity tiers, 0-10 health score and CI exit codes.
agent_created: true
---

# repocheck 仓库体检工具维护

## 概述

自包含桌面小工具：识别根目录下一级子目录里的项目，逐项做 **30 条体检**
（工程基建 / 文档完备度 / git 卫生 / CI 与 workflow 安全 / 凭据泄露 / 布局规范），
给出 **0–10 健康分**与严重度分级，支持 text / JSON / CSV / HTML 四种报告与
`--fail-on` 退出码。**全程离线**：只读本地文件 + 只读 git 命令，不联网、
不在项目里执行代码。运行时零第三方依赖。

复制优于共享：不 import 其他工具目录，也不依赖任何中心化共享核。

## 结构

| 文件 | 职责 |
| --- | --- |
| `main.py` | 入口分发 + Tkinter GUI（唯一 import tkinter 的地方） |
| `cli.py` | argparse / 四种输出 / 退出码 |
| `scanner.py` | 门面：`__version__` / `discover_projects` / `check_project` / `scan` / `dump_profile` |
| `scanctx.py` | `ProjectContext` 惰性索引 + 只读 git 封装 + 文本解码 |
| `rulebase.py` | `Severity` / `Rule` / `CheckResult` / 执行器 / 评分 |
| `rules_core.py` | 规则 1-8 |
| `rules_docs.py` | 规则 9-16 |
| `rules_vcs.py` | 规则 17/18/20/21/22/23/29 |
| `rules_ci.py` | 规则 19/24/25/26/27/28 |
| `rules_misc.py` | 规则 30 |
| `report.py` | text / csv / html / json 渲染 + 汇总 |
| `_optional.py` | 可选依赖能力探测（`find_spec`，不真 import） |
| `test_scanner.py` | pytest 用例 + 无 pytest 兜底冒烟 |
| `test_fixtures.py` | 声明式假仓库构造器 |

依赖方向单向：`main → cli → scanner → {scanctx, rulebase, rules_*, report}`。
`import scanner` 绝不触发 Tk。

## 常用命令

```bash
python -m pytest test_scanner.py -q     # 57 个用例（推荐）
python test_scanner.py                  # 无 pytest 时的兜底冒烟
python main.py --dump-profile           # 规则清单 + 可选依赖能力
python main.py --dump-profile --json    # 同上，机器可读（schema 2）
python main.py <工作区>                  # 命令行体检
python main.py <工作区> --fail-on error  # CI 门禁
python main.py <工作区> --workers 8      # 大批量时并发
python main.py                          # 启动 GUI
```

## 关键约定

- **规则即数据**：新增一条规则 = 在对应 `rules_*.py` 追加一个
  `Rule(id, key, label, criteria, severity, check, requires_git=..., requires=...)`。
  执行器、评分、`dump_profile()`、报告渲染会自动跟上，**不需要改控制流**。
- **规则 id 只增不改号**：`Scanner.RULES` 装配期会断言 id 从 1 连续且唯一；
  `--skip-rules` 与外部 Agent 都按 id 引用，改号等于破坏契约。
- **`dump_profile()` 前三个键固定**：`rules[]` 每条的前三个键必须是
  `id` / `label` / `criteria` 且顺序不变（已有 Agent 依赖）。新字段只追加。
- **新增规则要同步三处**：规则代码 + `README.md` 的规则表 + `test_scanner.py`
  的一条 `expect=` 断言。
- **纪律规则（项目特有，不要删）**：
  - 规则 7 旧仓库路径残留：检测目标串**运行时拼接**（`"D:" + "/allin"`），
    不能写成字面量，否则死根路径门禁会把检测器自己报成违规；
    文档里描述该规则时也用占位符（`<盘符>:/<旧工作区名>`）。
  - 规则 8 内联引擎副本缺 `engine.patch.yaml`。
- **import 断裂是启发式**：只看顶层模块名是否在项目内 / 标准库 /
  `COMMON_THIRD_PARTY` 手写清单。误报允许，标签带「疑似」。
- **跳过项必须压上限**：`skip` 不计入评分分母，但要按情形压低分数上限
  （无 `.git` → 6.0；截断/降级/异常 → 9.0），否则「越残缺分越高」。

## 已知陷阱

- **排除目录在 `DEFAULT_EXCLUDE`**：新增大目录（虚拟环境、构建产物、包安装目录）
  记得加。`.venv` 之类一旦漏掉，索引与 import 扫描会严重失准 —— v1 就吃过这个亏。
- **巨型仓库要限流**：文件索引 2 万、import 解析 800 个 `.py`、密钥与旧路径扫描
  各 1500 个文件。这些上限不是随便定的，取消会直接拖垮整次扫描。
- **文本读取先嗅探再读全文**：`ProjectContext._read_text` 只读前 4KB 判断 NUL。
  改成「先读全文再判断二进制」会让上万文件的仓库慢好几秒。
- **git 子进程是主要成本**（Windows 约 100ms/次）。不要为单条规则新增独立的
  git 调用；能复用 `ctx.git.ls_files` / `ctx.git.tags` 就复用，
  能提前 `skip` 掉就不要触发。
- **GBK 控制台**：`test_scanner.py` 与 `cli._ensure_streams()` 都做了
  `reconfigure(encoding="utf-8")`；新增入口别忘了。
- **windowed exe 无 stdout**：`repocheck.exe`（`console=False`）下 `sys.stdout`
  为 `None`，任何 `print` 都会崩。CLI 场景请用 `repocheck-dbg.exe` 或加 `--output`。
- **windowed 下 subprocess 闪黑窗**：所有 `subprocess.run` 必须带
  `creationflags=CREATION_NO_WINDOW`（已封装在 `scanctx._run_git`，不要绕开它）。
- **项目识别限于一级子目录**：对单项目目录本身扫描会返回 0 个项目，这是预期行为
  —— 请传它的父目录。
- **`*.spec` 已纳入版本库**：构建配置需要可复现，不要再加回 `.gitignore`。
