# Cordis 理论笔记 v2（2026-08-27 扩充）

> v1 来源：E:\docs 蛇棋实验区调研 + private-radio-stations/video/docs/HARNESS_NOTES.md（2026-08-24）。
> v2 增补来源（2026-08-27）：①官方指南 cordis.moe/zh-CN/guide/（理念/基础/加载器/进阶 16 页 SSR 全文，本文吸收：可逆插件系统、服务与依赖、生命周期三章）；②DeepSeek Harness 官方 Cordis 入门（reference/cordis-primer）；③DeepSeek Harness Hub 社区教程目录（插件/生命周期与服务/事件/配置/HMR）；④源码阅读 iceyao.com.cn/2026/08/14/cordis-source-code-read（Context 五核心服务与 Fiber 实现）；⑤技术栈 jishuzhan Day18《Cordis 框架：为可逆软件系统而生的元框架》（起源与演进史）；⑥CSDN 与知乎两篇未能抓取（反爬），链接保留待补。

## 1. 论文：《A Programming Paradigm for Spatiotemporal Composability》（2026-08-13 预印本，约 88 页）

- 作者：Yifan Shi、Wei Zhang（北京大学）、Tianyi Cui（DeepSeek-AI）。
- 核心主张：把类型论的 **effect / coeffect** 从编译期静态分析提升为**运行时机制**，为动态组合建立形式化基础，并以此实现框架 Cordis。
- 时间可组合性（Temporal）：组件移除时副作用必须**完全可逆回滚**——每次上下文变换携带逆操作，卸载时逆序自动调用。
- 空间可组合性（Spatial）：依赖被**声明、发现、反应式协调**——`inject` 声明，依赖到位即激活、消失即停用。
- 统一为单一上下文类型（Context），5 个元定理；关键的是**合流定理（Theorem 73）**：系统静止态 == 从零静态装配的态（动态增删与静态装配殊途同归）。

## 2. 形式化补充：effect / restore 的群结构（官方文档「可逆的插件系统」）

- 把带副作用的函数 f: X→Y 改写为 f: C×X→C×Y（C = 副作用的类型）；只看副作用得函数空间 F = C→C。
- F 在函数结合 ∘ 下构成**幺半群**（封闭性/结合律/单位元 id）；要求每个副作用可回收（存在逆元 f⁻¹）后构成**群**。
- 「副作用 = 资源占用」：打开文件/子进程/监听端口/注册回调/分配内存——资源天然可复用，故副作用必可逆。
- `effect` 把逆操作从返回值中分离：effect f (c, h) = (f(c), h∘f⁻¹)；可证 effect 是同态：effect(f∘g) = effect f ∘ effect g。
- `restore = (c, h) ↦ (h(c), id)` 即 effect 的逆——`restore(ctx)` 回收该上下文上的全部副作用。
- 全局环境的递归定义：C_{n+1} = C_n × (C_n→C_n)——每层包含上层状态并记录上层副作用；上下文对象（Context）就是把 C 显式化：插件挂载从当前上下文**派生子上下文**，子上下文管理插件内全部副作用，插件整体作为父上下文的一条副作用。
- 三分类：**不产生副作用的是库（Library）；产生副作用的是插件（Plugin）；能管理副作用的是框架（Framework）**。资源安全 = 副作用可完整回收；内存安全只是资源安全的一种（Rust 所有权 = 语言层强制；Cordis 上下文 = 应用层非强制）。框架两大优势：**无感性**（领域方法封装后开发者自然写出资源安全插件）与**渐进性**（API 可逐步资源安全化）。

## 3. 起源与演进（jishuzhan Day18 + 官方资料）

- Cordis（拉丁语「心」）= **元框架**（构建框架的框架）：不耦合业务，只解决「组件安全组合、热插拔、卸载完整逆转副作用」。作者 Shigma（Koishi 作者），cordiverse 组织，MIT，TypeScript。
- 演进线：Koishi 聊天机器人框架（插件即一切 + 运行时热更新）→ 插件系统抽离为通用基础设施 Cordis → 2025 年 DeepSeek Harness 采用进入大众视野 → 2026-08 北大与 DeepSeek-AI 论文形式化。
- 实证：基于 Cordis 的 Koishi 服务**三年无数插件更新、进程从未重启**。
- 事务化加载：配置更新时原子性加载新配置，任何步骤失败整体回滚，无「装了一半」残局。
- Fiber 状态机：每个插件独立生命周期状态机 `PENDING → LOADING → ACTIVE → DISPOSED`，状态转换确定。
- DeepSeek Harness 关系（v1 澄清沿用）：DeepSeek **不是作者**，是把 Cordis 用作 agent 运行时的 vendor 并加固（Fiber 重入、HMR）；「没有特权核心」——模型适配器/工具/沙箱/Web UI/agent loop 全是插件，`cordis.yml` 即配置清单。

## 4. 概念映射表（v2：补官方文档细节）

| Cordis 概念 | 语义（官方文档补充） | 本仓库对应物 |
|---|---|---|
| Context | Proxy 包裹的原型链对象；服务容器；三个刻画维度：副作用上下文（插件）/ 服务上下文（依赖）/ 会话上下文（过滤器） | alloy Context / radio·video 应用根 |
| Service | IoC 式实现（非 DI）；三类：框架自带（ctx.model）/框架定义未实现（ctx.database，插件以 `xxx-<服务名>` 命名实现）/插件定义实现（ctx.console）；`Context.service()` 声明 + `Service` 子类 `super(ctx, name, immediate)` + `start/stop/fork` 三钩子；插件卸载即服务移除 | ctx.provide 注册表；插件协议 inject |
| inject | 数组 = 必需依赖（服务 truthy 前不加载；值变化**立即回滚**；回滚后值仍 truthy 则重载）；对象 `{required, optional}` = 可选依赖（生命周期不依赖，运行时判空）；`ctx.inject()` = 部分功能依赖的子插件语法糖（⚠️ 内外两个 ctx 不能混用，否则热重载内存泄漏） | 插件协议 inject + 装配期校验 |
| caller / Context.current | 服务方法内 `this[Context.current]` 指向访问者上下文——在其上挂 dispose 即可回收「调用方」产生的副作用 | 平台调用的审计来源设计 |
| Fiber | 插件心脏：effect 栈 `disposables`，卸载 `splice(0).reverse()` **逆序、串行（task=task.then(dispose)）、可等待**回收；PromiseLike 包装 | Context dispose 栈 |
| Registry | 一插件一 Fiber；重复 plugin() 去重（不可重用只执行一次）；`registry.delete(plugin)` 移除全部副作用 | cordis.yml 注册表 |
| fork 事件 / reusable | `reusable=true` = fork 语法糖；fork 把插件切成外（执行一次，不可重用部分）内（每次调用，可重用部分）两个作用域；嵌套规则：不可重用内嵌可重用需用 fork 事件，可重用内嵌不可重用具自然 | 多实例装配方案 |
| ready / dispose 事件 | ready：异步初始化（文件/网络/等其它插件）；dispose：手动清理 ctx 之外引入的副作用 | 服务 start/stop 钩子 |
| isolate / 服务隔离 | 为特定服务创建隔离上下文，内外插件互不可感知（多租户/沙箱） | Context.child() 作用域 |
| Loader / HMR | 配置即数据；--watch：Fiber.dispose/update + provider 级联重载（@cordis/loader 才带文件监听） | cordis.yml；P8 留将来 |
| peerDependencies 区分 | npm 依赖 ≠ 服务依赖：服务是一对多、inject 下缺失不崩溃；仅导类型 → devDependencies；导入运行时内容（如 DataService 基类）→ 同时声明 peerDependencies | 插件市场元数据 |

## 5. 源码层实现速览（iceyao 源码阅读）

- `Context` 构造（packages/core/src/context.ts，十几行）：`new Proxy(this, ReflectService.handler)`；核心五服务全挂同一上下文：**Fiber**（生命周期状态机 + effect 回收，一插件一 Fiber）、**Reflect**（服务注册表，同时是 Proxy 的陷阱处理器）、**Registry**（插件注册）、**Events**、**Logger**。
- `Registry`：`new Fiber(ctx, config, Inject.resolve(plugin.inject), runtime, getOuterStack)`——依赖解析在装配期完成；Fiber 被包成 PromiseLike。
- `Fiber.effect(execute, label)`：收集执行结果、处理异步 effect、返回带 then 的 wrapper；卸载 = 逆序串行 dispose。
- 一句话：**一切皆 effect——副作用显式化，卸载时逆序、串行、可等待地回收**。

## 6. 生命周期事件速查（插件开发视角）

| 事件 | 触发 | 用途 |
|---|---|---|
| ready | 应用启动（已启动则挂载即触发） | 异步初始化、等待其它插件 |
| dispose | 插件停用（fork.dispose()） | 清理 ctx 之外的副作用 |
| fork | 插件每次被调用 | 可重用共享状态（外=一次/内=多次） |

## 7. 调试铁律（v1 四条沿用 + v2 增补）

1. inject 守卫：Service 回调里访问 `ctx.xxx` 必须 `static inject` 声明，否则运行时抛错。
2. 同帧抢占：手动 set 无效先查同事件其它监听器是否同帧覆盖。
3. HMR 正确姿势：Fiber.dispose/update + provider 级联重载。
4. 重开叠加泄漏：reset 类路径重应用前先回收上一轮监听器/定时器。
5. **子插件 ctx 陷阱**：`ctx.inject(['x'], (ctx) => ...)` 回调内必须用参数 ctx，用外层 ctx 会在服务热重载时内存泄漏。
6. **caller 纪律**：服务方法要回收「调用方副作用」时，挂在 `this[Context.current]` 的 dispose 上，而不是挂在服务自身。

## 8. 落地清单（对工作区项目）

- private-radio-stations：把 radio/video/portal 三簇的服务注册统一为 `Service` 子类化（start/stop/fork 三钩子）+ `inject {required, optional}` 声明，替代散装 cordis.yml 手工顺序；利用事务化加载做装配原子性；服务方法内部用 caller 纪律处理跨插件副作用。
- E:\lab chess-cordis：已实践「宿主不 import 子项目 + JSON-stdio 子进程 + 热插拔」，与官方「服务隔离」同构——可把 10 语言引擎注册为 10 个 Service，依赖注入（引擎就绪→harness 激活）直接映射 inject。
- alloy（Python 微内核）：effect/dispose 栈已同构；**fork 双作用域已落地（2026-08-27）**——`Context.fork(name)` 命名作用域（销毁自动摘除、同名重复抛 DuplicateScopeError）、`Context.fork_install`（outer 只执行一次 + apply 每次独立 fork，多实例玩法复用）、`GameEngine.mount_scoped/unmount`（WorldLog 记录 plugin.mount/plugin.unmount）；测试 +10（379 项，fork 10/10 绿）。
- 平台 registry（allin-platform）：platform.yaml 的 publish/launch/stop 已升级为 Cordis 风格清单（inject 依赖 + 事务化装配 + 服务隔离）——**stop 字段 dispose 纪律已落地（2026-08-27）**：stopEntry 优雅停止优先（entry.stop.command + 2s 回弹窗口）回退树杀，退订先停后删，/api/shutdown 前 shutdownAll 回收；E5 订阅方落地为 portal 告警页签（/api/alerts 聚合各项目 divergence-events.jsonl）。