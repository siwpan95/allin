# reposcan/ — 工作区发布区（`repos/`）仓库分类工具链（2026-10-28 并入）

对发布区（仓根的同级目录 `repos/`，默认 `<仓根>/../repos`）下的全部仓库做
「README + 代码信号」双维分类的工具链：**领域**（12 大类）× **技术栈**（语言 / GUI / 架构 / 依赖库），
每仓附 README 证据可回溯。

> **路径不写死盘符**（SPEC-001 §铁律 5）：发布区根由 `ALLIN_REPOS` 环境变量指定，
> 未设置时取仓根同级的 `repos/`，都定位不到即响亮退出（宁可不跑，也不静默扫错目录）。
> 中间物与产物的落点一律锚在本目录 —— 从哪个目录调用都写到同一处。换机或克隆后无需改代码。

## 安装 / 快速开始

标准库零依赖，克隆即可用（无需 pip install）：

```bash
# 指向非默认发布区时（可选）
export ALLIN_REPOS=/path/to/repos
```

## 用法 / 示例

流水线按顺序跑四步：扫描 → 技术栈探测 → 交叉索引总表 → 矩阵热力表。

```bash
# ① 扫描：各仓 README + 顶层文件 → repos_meta.json
python tools/reposcan/scan_repos.py
# ② 技术栈信号：依赖文件 + import → tech_meta.json
python tools/reposcan/detect_techstack.py
# ③ 交叉索引总表 → output/repos_master.md
python tools/reposcan/build_master.py
# ④ 矩阵热力表 + CSV + XLSX → output/（需 openpyxl）
python tools/reposcan/build_matrix.py
```

辅助脚本：`compact.py`（摘要浏览）、`classify.py`（领域分类报告）、`generate_final.py`（双报告）、
`tech_view.py`（技术栈视图）、`deep_probe.py`（边界仓深挖）。

## 工具链

| 脚本 | 作用 | 依赖 |
| --- | --- | --- |
| `scan_repos.py` | 批量抓取各仓 README + 顶层文件 → `repos_meta.json` | 标准库 |
| `detect_techstack.py` | 依赖文件 + import 信号 → `tech_meta.json`（lang/gui/arch/deps） | 标准库 |
| `compact.py` / `classify.py` | 摘要浏览 / 领域分类报告（人工判定表内置） | 标准库 |
| `deep_probe.py` | 边界仓深挖（结构树 + README + 入口源码） | 标准库 |
| `tech_view.py` / `generate_final.py` / `build_master.py` | 技术栈视图 / 双报告 / 合并交叉索引总表 | 标准库 |
| `build_matrix.py` | 矩阵热力表 + CSV + XLSX 导出 | **唯一例外：需 openpyxl**（XLSX 部分；HTML/CSV 部分零依赖） |
| `_root.py` | 共用路径定位（发布区根 / 中间物 / 产物落点） | 标准库 |

> 铁律注记：本目录脚本按 `tools/` 约定应零三方依赖，`build_matrix.py` 因 XLSX 导出
> 需要 `openpyxl`（import 处已做显式提示）。其余脚本拷走即可用。

## 产物（本机生成，不入库）

渲染结果与扫描中间物都是**可重生成的本机产物**，按仓根 `.gitignore` 约定不入库
（与 `/目录索引.txt`、`/tools/gate/audit/*` 同一口径）：

| 文件 | 内容 |
| --- | --- |
| `repos_master.md` | 单份交叉索引总表：主总表（领域+技术栈全字段）+ 领域分组 + 技术栈分组（标签后附领域） |
| `repos_master_matrix.html` | 领域×技术栈矩阵热力表（按列归一化上色） |
| `repos_master.csv` | 全字段 × 24 列，utf-8-sig，Excel 直开 |
| `repos_master.xlsx` | 双 sheet（总表带 auto_filter+冻结首行；矩阵复刻热力上色） |

**入库的资产是判定表本身**：各仓的领域 / 子类 / 技术栈人工核定结论，落在
`build_master.py` 与 `build_matrix.py` 内置的 `CAT` 字典里，随源码入库；
上表四件产物是它的渲染结果，跑一遍流水线即可在本机再生。

## 许可

本目录随仓根 `LICENSE`（MIT-0）授权；`build_matrix.py` 的 `openpyxl` 为运行时可选依赖，
不随仓分发。
