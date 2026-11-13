# registry 分类词表（唯一事实源 · v2 · 2026-11-13）

> **机器可读权威版**：`platform/registry/categories.yaml`（与本文同源维护，改一处须同步另一处；本文为人类可读孪生）。

> **时点** 2026-11-13 建档（v1 的 8 类枚举 → v2 的 13 类；`write` 由 `tool` 改归 `content`）
> **留痕** [交接卷 2026-11](../记录/交接/2026-11.md)（第一百六十八节）· [记忆月账 2026-11](../记录/记忆/2026-11.md)
> **观测工具/命令** `platform/registry/projects/*.yaml` 逐条读 `category` 字段 ＋ 与 `docs/事实源/tiering.yaml` 的 `domain` 字段对账
> **失效条件** 任一条目的定位变更，或词表增删分类项 —— 届时须整表重核
> **上位规则** [`../规范/SPEC-001-铁律.md`](../规范/SPEC-001-铁律.md)（铁律 1 README 优先 / 铁律 5 去符盘）；分级决策见 [`组合分级决策索引.md`](组合分级决策索引.md)
> **去符盘口径**：本文件不写死任何盘符；工作区 repos 根按机器而异，各机以自身 `git rev-parse --show-toplevel` 上级目录为准。

> **本表的定位**：`platform/registry/projects/*.yaml` 的 `category` 是**面向机器的受控枚举**（本表是它的唯一权威定义）。
> 它与另外两套分类的关系：
> - [`工具分类索引.md`](工具分类索引.md) —— **面向人**的用途速查（七类），与本表**不一一对应**（刻意分层，非漂移）；
> - [`组合分级决策索引.md`](组合分级决策索引.md) / `tiering.yaml` 的 `domain` —— **面向决策**的领域判断（140 条逐仓）。
> 本表取「**它是什么（类型）**」为判据；`tiering.domain` 取「**它服务于什么领域**」为判据 —— 两者可不同，不算矛盾。

---

## 一、词表（13 类）

| id | 中文 | 覆盖范围 | 外部锚点 |
|---|---|---|---|
| `game` | 游戏作品 | 可玩成品 —— 单机/跑团应用/棋类/放置挂机/视觉小说平台 | Wikipedia: Video games ｜ GitHub Topics: Game Development |
| `engine` | 引擎/框架 | 引擎、内核、底层框架、插件宿主与引擎演示集 | Wikipedia: Programming tools · Libraries ｜ GitHub Topics: Game engine, Library |
| `ai` | AI/大模型 | 生成式与 Agent 栈 —— 文本生成、叙事引擎、创作智能体 | Wikipedia: AI software ｜ GitHub Topics: Machine learning, LLM |
| **`content`** | **内容/创作** | **内容资产与创作工作区** —— 正文、设定、素材、写作工作区、视觉小说阅读端 | Wikipedia: Content management ｜ awesome-repositories: Content Management & Publishing |
| `media` | 视频/图像/特效 | 图像与视频的处理、生成、渲染与视觉小工具 | Wikipedia: Multimedia software · Graphics software ｜ GitHub Topics: Data visualization |
| `music` | 音乐/音频 | 音频合成、混音、采样、音色工程与电台 | Wikipedia: Music software |
| **`player`** | **播放器** | **媒体运行时与播放器宿主**（多端统一宿主、插件版播放器、本地/每日/音乐播放器） | Wikipedia: Application software · Multimedia software |
| `crawler` | 爬虫/采集 | 抓取、下载、站点采集与素材抓取 | Wikipedia: Data acquisition ｜ GitHub Topics: Browser Automation & Scraping |
| `tool` | 开发者/系统工具 | 通用工具与库 —— 打包器、测试器、文档工具、图形小工具等 | Wikipedia: Computer programming tools ｜ GitHub Topics: CLI, Utilities |
| **`automation`** | **工具链/自动化** | **流水线、发布归档、扫描登记、批量调度与定时任务** | Wikipedia: Build automation ｜ GitHub Topics: Automation, DevOps & CI/CD |
| `platform` | 平台/集成 | 集成平台、门户、按需启动的统一入口 | Wikipedia: Middleware |
| **`prototype`** | **原型/学习/实验** | **原型仓、多语言移植验证场、实验性作品与已退役的叙事原型** | 仓内判断：`tiering` 领域「原型/学习/杂项」「多语言引擎移植验证」 |
| `unclassified` | 未分类 | **机器自动发现、尚未人工定类**的条目（`discover_repos.mjs` 的自动产出） | 仓内判断：`discover_repos.mjs` 的默认占位值 |

> **加粗四类为本轮新增**（v1 只有 8 类：`game` / `tool` / `media` / `crawler` / `ai` / `music` / `engine` / `platform`）。

---

## 二、判据与边界

1. **类型优先、用途次之**：归类看**它是什么**，不看它服务什么场景。
   同一领域可以散布多类：`novel` / `novel-generator` / `weor` / `write-agent` 都是小说域，但它们是**生成器** ⇒ 归 `ai`；
   `write` 是**成品内容仓** ⇒ 归 `content`。
2. **容器归其域**：`dev-toolkit` / `game-prototypes` / `media-prototypes` / `music-prototypes` 四个 ③b 归档聚合仓
   仍留在各自域类（`tool` / `game` / `media` / `music`）—— 它们是**分级层的容器**，不该由 `category` 表达。
3. **`unclassified` 是合法值**：`platform/scripts/discover_repos.mjs` 自动登记的条目一律先落 `unclassified`，
   等人工定类后改写。v1 把「受控枚举」写成 8 类时漏了这一项，实际一直存在。

---

## 三、本轮重分类清单（19 条，依据＝`tiering.yaml` 的 `domain` 领域判断）

| id | 原 category | 新 category | 依据（tiering 领域） |
|---|---|---|---|
| `write` | `tool` | **`content`** | 用户定：内容/创作域（本仓为网文创作与素材工作区） |
| `novel-reader` | `game` | **`content`** | 小说/网文 |
| `3dworld-demos` | `game` | **`engine`** | 游戏引擎/框架 |
| `3dworld-globe` | `media` | **`engine`** | 游戏引擎/框架 |
| `cordis-snake` | `game` | **`engine`** | 游戏引擎/框架 |
| `cordis-text-game` | `game` | **`engine`** | 游戏引擎/框架 |
| `dict-scene-engine` | `game` | **`engine`** | 游戏引擎/框架 |
| `lab` | `game` | **`prototype`** | 多语言引擎移植验证 |
| `weiqi-lab` | `game` | **`prototype`** | 多语言引擎移植验证 |
| `sin-virtue-cordis-host` | `game` | **`prototype`** | 原型/学习/杂项 |
| `sin-virtue-game` | `game` | **`prototype`** | 原型/学习/杂项 |
| `players-unified` | `media` | **`player`** | 播放器 |
| `pluginplayer` | `media` | **`player`** | 播放器 |
| `musickit` | `media` | **`music`** | 音乐/音频 |
| `radio` | `media` | **`music`** | 音乐/音频 |
| `gan` | `ai` | **`media`** | 视频/图像/特效 |
| `procedural-video` | `ai` | **`media`** | 视频/图像/特效 |
| `video-generator` | `ai` | **`media`** | 视频/图像/特效 |
| `dsh-release-archiver` | `tool` | **`automation`** | 工具链/自动化 |

> **`tool` 桶内的主题细分本轮不做**：它同时承担「B 级可打包交付」的功能语义（见 §4 耦合），
> 把 `bloodmusic`（音频）、`ollama-generator`（AI）、`worldbuilder`（引擎）等移出 `tool` 会改变
> `build_batch.mjs` 的缺省批量打包范围 —— **属独立的一笔解耦**（把打包范围从 `category` 里摘出来），
> 不与词表扩充混做。已在交接卷登记为待办。

---

## 四、已知耦合（改词表前必看）

`platform/scripts/build_batch.mjs` 的缺省批量打包范围 ＝ `category == 'tool'`：

- 本轮重分类后该范围由 **47 → 45**，但**实际打包行为不变** ——
  离开范围的 `write`（`launch.command: explorer .`）与 `dsh-release-archiver`（`bash scripts/run.sh`）
  **本就没有 Python 入口**，脚本的 `entryScript()` 判不出入口 ⇒ 从未产出过包。
  （实测 `platform/release/` 目录为空。）
- 若后续要把 `player` / `media` / `music` 里的 Python GUI 仓也纳入打包，**须先解耦**：
  把「可打包」从 `category` 独立成显式字段或清单，再改分类。

---

## 五、借鉴记账（治理准则：借鉴必记账）

| 来源 | 许可证 | 借用范围 | 本仓用法 |
|---|---|---|---|
| Wikipedia《List of software categories》 | **CC BY-SA 4.0** | 词表的**形状** ——「应用软件／系统软件／编程工具」三分与其细类命名（Application software · Multimedia software · Music software · Graphics software · Video games · Data acquisition · Computer programming tools · Build automation · Middleware · Content management） | 只借**分类思路与命名**，不复制正文；本表的分类项按本组合实况裁剪 |
| GitHub Topics 官方标签体系 | GitHub Terms（公开标签目录） | 主题级标签口径（Game Development · Machine learning · Game engine · Library · Automation · DevOps & CI/CD · Browser Automation & Scraping · CLI · Utilities · Data visualization · LLM） | 同上，只借**标签口径**，不复制内容 |
| awesome-repositories.com 分类树 | 公开目录（条目各自许可） | 「Content Management & Publishing」这一类目名 | 仅用于 `content` 类的**命名参照** |

> 本组合的**粒度判据**不来自外部，而来自仓内权威：`docs/事实源/tiering.yaml` 的 `domain` 字段（140 条逐仓领域判断）。
> 外部词表只提供「有哪些类、怎么命名」的骨架，**归类结论一律以仓内事实为准**。
