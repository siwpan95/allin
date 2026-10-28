# reposcan/ — `D:\projects\repos` 仓库分类工具链（2026-10-28 并入）

对 `D:\projects\repos` 全部 **133 个仓库**（原 134，`sin-virtue-game` 已于远端+本地删除后同步剔除）
做「README + 代码信号」双维分类的工具链与产物：**领域**（12 大类）× **技术栈**（语言/GUI/架构/依赖库），
每仓附 README 证据可回溯。

## 产物（`output/`，只增不改）

| 文件 | 内容 |
| --- | --- |
| `repos_master.md` | 单份交叉索引总表：主总表 133 行（领域+技术栈全字段）+ 领域分组 + 技术栈分组（标签后附领域） |
| `repos_master_matrix.html` | 领域×技术栈 24 属性矩阵热力表（按列归一化上色） |
| `repos_master.csv` | 133 行 × 24 列，utf-8-sig，Excel 直开 |
| `repos_master.xlsx` | 双 sheet（总表带 auto_filter+冻结首行；矩阵复刻热力上色） |

## 工具链（按流水线顺序）

| 脚本 | 作用 | 依赖 |
| --- | --- | --- |
| `scan_repos.py` | 批量抓取各仓 README + 顶层文件 → `repos_meta.json` | 标准库 |
| `compact.py` / `classify.py` | 摘要浏览 / 领域分类报告（人工判定表内置） | 标准库 |
| `detect_techstack.py` | 依赖文件 + import 信号 → `tech_meta.json`（lang/gui/arch/deps） | 标准库 |
| `deep_probe.py` | 边界仓深挖（结构树 + README + 入口源码） | 标准库 |
| `tech_view.py` / `generate_final.py` / `build_master.py` | 技术栈视图 / 双报告 / 合并交叉索引总表 | 标准库 |
| `build_matrix.py` | 矩阵热力表 + CSV + XLSX 导出 | **唯一例外：需 openpyxl**（XLSX 部分；HTML/CSV 部分零依赖） |

> 铁律注记：本目录脚本按 `tools/` 约定应零三方依赖，`build_matrix.py` 因 XLSX 导出
> 需要 `openpyxl`（import 处已做显式提示）。其余脚本拷走即可用。

## 重跑方式

```bash
# 扫描（ROOT 常量在脚本内，指向 D:/projects/repos）
python tools/reposcan/scan_repos.py
python tools/reposcan/detect_techstack.py
# 产物重建（脚本把 md/html/csv/xlsx 写到当前工作目录；入库版本在 output/，重跑后请同步覆盖）
python tools/reposcan/build_master.py
python tools/reposcan/build_matrix.py   # 需 openpyxl
```

分类判定表（`build_master.py`/`build_matrix.py` 内置 `CAT` 字典，133 仓）为人工核实结果，
边界仓结论见 `output/repos_master.md` 头部说明与当日工作日志。
