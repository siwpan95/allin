# media_engine 立项报告（P3 · 按 alloy 路线）— 2026-08-24

> 按铁律 0：先读 media 群各 README + media_engine 遗骸 README，再立项。
> 状态：立项完成 + **阶段 A 已执行（2026-08-24）**：pywallpaper 纯加法三件事升级落地（core/context.py + core/world_log.py 内联自 alloy；main.pyw --dump-profile/--dump-log；运行级 run_start/run_end 日志；test_three_things.py 3/3；其既有 test_engine.py 5/5 无回归）。阶段 B/C 待拍板。

## 一、README 揭示的事实（立项前提修正）

1. **media_engine 不是失败，是成功迁移**（其 README 2026-08-21）：48 个效果中 **47 个已迁入 pywallpaper**，GUI 被 pywallpaper 替代，本体移入 media/_archive 仅供查阅。
2. **pywallpaper 已是事实上的统一媒体引擎**（README）：ECS 架构（Entity/Component/System/World）+ JSON 内容层（54 个效果配置与逻辑完全解耦）+ 装饰器/子类**自动发现零硬编码注册** + 公式引擎（含 asteval）+ CA（4973 配方自包含）+ 粒子/流体原语；draw 的配方库已收归其 recipes/（2026-08-21），draw 可随时归档。
3. 其余项目：shikonghuaban = 独立可视化（黑洞/Penrose，particle/ 子包**内联**=复制优于共享）；cellular_automaton = 独立（142 规则 pygame+numpy，全量测试）；photo = 图片爬虫（14.1.0，属于 crawler 群成员，**不是媒体引擎素材**）。

## 二、立项结论

**P3 立项对象修正为：以 pywallpaper 为 media 引擎本体，按 alloy 三件事模板升级；不做任何新融合。**

| 项目 | 处置 | 理由 |
|---|---|---|
| **pywallpaper** | 🧩 升级为媒体引擎本体（下方阶段 A） | 已是统一引擎，缺 alloy 三件事的纪律化外壳 |
| shikonghuaban | 保持独立；其 particle/ 内联副本维持现状 | 复制优于共享；特定主题可视化 |
| cellular_automaton | 保持独立；通用 CA/主题层未来可内联引擎能力 | 独立完整、全量测试 |
| photo | 保持独立（crawl_hub 成员） | 爬虫不是媒体引擎 |
| media_engine 遗骸、wallpaper1/2、lap、log、yuanbao、create、art | 维持归档/观察（wallpaper1/2 为 merge 候选，见阶段 C） | 不动 |

## 三、pywallpaper 与 alloy 模板的差距（升级清单）

| alloy 三件事 | pywallpaper 现状 | 差距 |
|---|---|---|
| 注册即回滚（Context/dispose） | 装饰器 + 子类自动发现注册（零硬编码） | 无显式 Context 内核与卸载回滚语义 |
| 补丁即差异（patch/dump-profile） | JSON 内容层已与逻辑解耦（54 effects） | 无"装配树自描述"CLI（dump-profile 等价物） |
| 日志即事实源（WorldLog） | 性能监控（wallpaper_system） | 无追加式事件日志/回放 |
| sync/审计 CLI | — | 无 |

**升级方案（阶段 A）**：在 pywallpaper 内**加法式**新增（不破坏现有自动发现）：
1. `core/context.py`：Context 微内核（直接内联 alloy 的 core/context.py——复制优于共享，标注来源）；
2. 效果注册接入 Context（自动发现的注册动作压入 dispose 栈，热切换主题=卸载旧效果注册）；
3. `core/world_log.py`：WorldLog（效果轮换/主题切换/音频事件入日志，审计与调试）；
4. `cli.py --dump-profile/--dump-log`：装配树与事件日志自描述（agent 审计入口）；
5. ECS 决策点：pywallpaper 自带 ecs.py 与 alloy core/ecs.py 并存——**暂不合并**，立项期保持各自演化，待引擎收敛评估（避免现在动两套成熟代码）。

## 四、阶段计划与验收

| 阶段 | 内容 | 验收 |
|---|---|---|
| A | pywallpaper 三件事升级（上表 1-4，纯加法） | 现有全量测试不回归 + 新增 context/log 测试 + dump-profile 可输出 54 效果清单 |
| B | 内联纪律：若 shikonghuaban/cellular_automaton 未来引用引擎能力 → 内联副本 + engine.patch.yaml（照 games 六副本模式） | 引用项目测试全绿 |
| C | 归档候选清单：wallpaper1/2（MERGE_PLAN 候选，README 显示待合并）、media_engine 遗骸（已归档）→ 逐案确认 | 清单报用户确认后执行 |

## 五、风险与边界

1. **不融合**：shikonghuaban/cellular_automaton/photo 一律独立运行；pywallpaper 只做"能力提炼"，不做"项目吞并"（helminth 教训仍有效）。
2. **ECS 双轨**：pywallpaper 自有 ecs.py 与 alloy 的 core/ecs.py 并存是刻意的——立项期不合并，避免两套成熟代码同时动刀。
3. 依赖面：pywallpaper 依赖 numpy/numba/pygame（壁纸渲染），引擎化后核心与效果层分层保持现状（core 零重依赖）。

## 六、待拍板
1. 是否按阶段 A 启动 pywallpaper 三件事升级（纯加法，可回滚）？
2. wallpaper1/2 是否纳入阶段 C 归档候选？
3. ECS 双轨是否长期保留（或未来指定一个为唯一 ECS）？
