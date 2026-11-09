# allin × GraphRAG 语料与降级说明（待落仓骨架）

> 定位：**叙述层的全局/多跳问答**。绝不用来回答结构化取值。
> 依据：microsoft/graphrag（MIT），**v3.3.0 / 2026-10-14，官方 README 明说已进入
> "largely in maintenance mode"、定位 research demo 而非生产服务**（这是选型风险，不是缺点列表）。
> 运行要求 Python 3.11–3.13（**3.14 不支持**）；本机 `E:\Python314\python.exe` = 3.13.14 ✅ 刚好在窗口内。
> 论文 <https://arxiv.org/pdf/2404.16130v2.pdf> · 官方文档 <https://microsoft.github.io/graphrag/>

## 1. 语料边界（这是与"事实源数据库化"不冲突的前提）

| 域 | 进 GraphRAG 吗 | 理由 |
|---|---|---|
| `docs/规范/`（SPEC 系列） | ✅ | 规则、理由、沿革，适合多跳「为什么现在是这样」 |
| `docs/记录/`（交接/决策/专题/事故/审计） | ✅ | 叙述性最强，全局主题与事件链 |
| `architecture/adr/`、`CHANGELOG.md`、`README.md` | ✅ | 决策与演进脉络 |
| `docs/事实源/*.md`（结构化取值 / 生成物） | ❌ | 数字交给 SQL，概率抽取会二次污染已核对的事实 |
| `docs/事实源/_structured/*.json`、`ports.yaml` | ❌ | 同上 |
| `docs/事实源/机器/*/附属/`（HTML/旧机报告） | ⚠ 单独评估 | 一次性原始件，非现行事实 |
| `docs/md/` 冻结历史树（231 篇） | ❌ 默认排除 | 冻结留证；除非专门做"历史考古"索引 |
| `tools/gate/audit/*.jsonl` | ❌ | 审计流水走 SQL，不进图 |

`build_input.py` 就是按上表从 Git tracked 文件生成 `input/*.txt` 的唯一入口（不手搬、不复制正文进仓）。

## 2. 命令序列

```bash
pip install graphrag                       # Python 3.10+；本机 E:\Python314 = 3.13.14 可用
graphrag init --root E:/allin-graphrag    # 生成 settings.yaml / .env / prompts/ / input/
# 用骨架的 settings.yaml 覆盖，并把 .env 的 GRAPHRAG_API_KEY 放仓外
E:/Python314/python.exe build_input.py --root D:/projects/allin --out E:/allin-graphrag/input
graphrag prompt-tune --root . --domain "个人项目治理与多机资产台账" --language Chinese
graphrag index --root .                    # 索引：TextUnit -> 实体/关系/claim -> Leiden 社区 -> 摘要
graphrag query --root . --method global --query "这套治理体系里，哪些判据是因事故补上的？"
graphrag query --root . --method local  --query "D17 留痕判据涉及哪些文件？"
graphrag query --root . --method drift  --query "多机事实混淆问题的来龙去脉是什么？"
```

## 3. 四种检索模式怎么选

| 模式 | 适用 | allin 的例子 |
|---|---|---|
| `basic` | 单跳向量基线 | 「D17 在哪个文件」 |
| `local` | 具体实体及其邻域 | 「g20 门禁关联了哪些事故记录」 |
| `global` | 全库主题 / 趋势（社区摘要 map-reduce） | 「这套治理体系的判据演进有哪几条主线」 |
| `drift` | 局部实体 + 全局脉络 | 「多机事实混淆问题从发现到闭环的全过程」 |

> 微软论文的结论只覆盖 **global sensemaking** 类问题的完整性/多样性优势；
> 独立评测（arXiv:2502.11371）指出单跳细节查询上基础 RAG 相当或更好，且图覆盖率、LLM-as-judge
> 位置偏差都是真实风险 ⇒ **结构化取值一律走 facts CLI / MCP，不走这里**。

## 4. 中文语料的具体坑

- `cl100k_base` 对汉字 token 化更贵 → `chunks.size` 调小（骨架里 600），先小语料试跑测成本；
- 默认实体抽取 prompt 是英文语境 → **必须 `graphrag prompt-tune --language Chinese`**，
  并把 `entity_types` 换成中文领域词（机器/门禁/规范/仓/决策/事故）；
- 索引阶段每个 TextUnit 至少一次 LLM 调用 + 每层社区摘要 → 成本随语料线性增长，
  官方自己建议先用便宜模型跑通再放量；抽取与摘要可用不同档位模型；
- 索引产物是 `output/` 下的 parquet（entities / relationships / communities / claims / text units），
  **全部不入库**，`.gitignore` 忽略；可离线复盘图结构；
- 增量更新代价高 → 叙述层按**月卷**增量索引，不要每次文档改动全量重建。

## 5. 三档降级（本仓硬要求，见同目录 `qa.yaml`）

治理门禁不得依赖任何在线服务。`qa.yaml` 由**自建 QA 封装层**读取（⚠ 不是 GraphRAG 官方
settings schema，塞进 settings.yaml 会被 Pydantic 校验拒绝）：

| 档 | 条件 | 结构化问题 | 叙述层问题 | 响应标注 |
|---|---|---|---|---|
| `full` | 索引 + LLM 可用 | facts_cli SQL | GraphRAG global/local/drift | `source_type=graphrag` |
| `offline` | 无 API key / 索引失败 | facts_cli（SQLite 可离线重建） | 现有 `mcp:docs.search`（BM25 + `file#L`） | `knowledge_index=offline` |
| `readonly` | 连 SQLite 都没有 | 直读 `facts.json` + Schema 校验 | 自建 SQLite FTS5 trigram / BM25 | `knowledge_index=readonly` |

⚠ **GraphRAG 的 `basic_search` 不能当离线降级**：它仍要 embedding provider + 已建向量存储。
`readonly` 档必须自建 BM25 / FTS5。GraphRAG **不进 `run_all_gates.sh` 的阻断链**。
三态分离：声明态（Git YAML）/ 意图态（Dolt + NetBox）/ 运行态（采集流水），
每个答案的 citation 必须带 `state_kind`，禁止三态混答。

## 6. citation 纪律

每条图检索答案必须带回 `source_file:line`；社区摘要只能作为**导航线索**，不能作为事实陈述。
若答案涉及数字、路径、状态值，必须再由 `facts.get` 用 SQL 复核一次并附上 `observed_at`，
否则按「无证据，拒答」处理（对齐 MCP README「调用成功 ≠ 任务完成」与 ADR-0003 只读纪律）。

## 7. 最小验收

1. `build_input.py --selftest` 证明结构化取值文件被排除、叙述层被纳入；
2. 20 条真实问题建回归集，其中 ≥5 条是全局/多跳，答案必须带 citation；
3. 抽掉 API key，`facts.query` 返回 `knowledge_index=offline` 且答案仍可用；
4. 同一问题分别问 GraphRAG 与 `facts.get`，数字类答案**逐字符相等**；
5. GraphRAG 完全停摆时，`scripts/run_all_gates.sh` 仍 20/20 全绿。
