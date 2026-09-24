# 用 allin_engine 重构 mahjong —— 详细方案（待确认）

> 范围：**仅替换基础设施层**（事件系统 / 计时循环 / 字体加载），领域逻辑（牌堆、布局、配对算法、计分、牌面绘制）**完全不动**。
> 原则：遵循「复制即复用」，把引擎副本**内联**进 `mahjong/allin_engine/`（同 dwarf_scrolls），不跨项目硬引用。

---

## 0. 结论速览

| 现状（mahjong 自研） | 重构后（用引擎） | 改动文件 |
|---|---|---|
| `viewmodel` 手写 `add_listener` / `_emit` 列表分发 | 引擎 `EventBus`（递归保护 + 容错 + 一次性监听） | `game_viewmodel.py` |
| `main.py` 用 `root.after(250)` + `time.time()` 搓计时 | 引擎 `FixedTimestepLoop`（固定步长、钳制死亡螺旋） | `main.py` + `game_viewmodel.py` |
| `tile_renderer` / `hud` 手写字体路径搜索 + 硬编码 `("SimHei",10)` | 引擎 `utils.font`（`discover_local_fonts` / `load_local_tk_font`） | `tile_renderer.py` + `hud.py` |

**不动**：`models/*`、`services/*`、`chess.py`、棋盘绘制/命中/动画逻辑、所有游戏规则与计分。

---

## 1. 嵌入引擎副本

引擎顶层导入已实测可在无 numpy/pygame 环境下安全加载（叶子模块零拖拽）。复制时**排除 `.git`**（避免嵌套仓库），保持"静态内联副本"而非 submodule。

```bat
rem 1) 复制引擎（排除 .git / 缓存），内联为 mahjong 的子包
robocopy "D:\allin\allin_engine" "D:\allin\right\mahjong\allin_engine" /E /XD .git __pycache__ .github /XF *.pyc

rem 2) 把 mahjong 自带字体并入引擎 fonts 目录，交给引擎字体发现机制托管
copy "D:\allin\right\mahjong\assets\SimHei.ttf" "D:\allin\right\mahjong\allin_engine\fonts\"
copy "D:\allin\right\mahjong\assets\Arial.ttf"  "D:\allin\right\mahjong\allin_engine\fonts\"
```

完成后 mahjong 以 `python main.py` 运行时，`allin_engine` 作为子目录可直接 `import`（与 dwarf_scrolls 一致）。
引擎自带手写体仍在 `fonts/`，与 SimHei/Arial 并存不冲突（发现机制按文件名 stem 区分别名：`simhei` / `arial` / `baocanmou...`）。

---

## 2. 事件系统替换（`game_viewmodel.py`）

**关键约束**：引擎 `EventBus` 无通配订阅，按事件类型注册；其回调签名是 `handler(data)`，而视图层现有 `_on_event(ev)` 依赖 `ev.type` / `ev.data` 信封。
→ **采用"薄适配"策略**：保留 `add_listener(fn)` 与 `GameEvent` 信封对外 API **不变**（视图层零改动），内部用 `EventBus` 承载分发。

```python
# 旧
Listener = Callable[["GameEvent"], None]
@dataclass
class GameEvent:
    type: str
    data: Dict[str, Any] = field(default_factory=dict)

class GameViewModel:
    def __init__(self, ...):
        ...
        self._listeners: List[Listener] = []

    def add_listener(self, fn): self._listeners.append(fn)

    def _emit(self, etype, **data):
        ev = GameEvent(etype, data)
        for fn in self._listeners:
            try: fn(ev)
            except Exception: pass
```

```python
# 新
from allin_engine.core.event_bus import EventBus

GAME_EVENTS = (
    "new_game","select","deselect","match","reject","hint","hint_empty",
    "shuffle","shuffle_empty","undo","undo_empty","win","lose","deadlock",
    "pause","resume","tick","mode_changed",
)

class GameViewModel:
    def __init__(self, ...):
        ...
        self._bus = EventBus()
        self._legacy_listeners: List[Listener] = []
        for _t in GAME_EVENTS:
            self._bus.subscribe(_t, self._make_dispatcher(_t))

    def _make_dispatcher(self, etype):
        def _dispatch(data):
            ev = GameEvent(etype, data if isinstance(data, dict) else {})
            for fn in list(self._legacy_listeners):
                try: fn(ev)
                except Exception: pass
        return _dispatch

    def add_listener(self, fn): self._legacy_listeners.append(fn)

    def _emit(self, etype, **data):
        self._bus.publish(etype, **data)   # 总线：容错 + 递归保护
```

收益：`board_canvas.py` / `hud.py` 的 `_on_event(ev)` **一字不改**；拿到引擎的递归保护与回调容错；`GAME_EVENTS` 顺手把散落字符串收敛成契约常量。

> 可选（更"现代"但改动大）：让视图直接 `vm._bus.subscribe("match", handler)` 并改 `_on_event` 签名。本次不采用，留给后续。

---

## 3. 计时循环替换（`game_viewmodel.py` + `main.py`）

把"墙钟时间"从 ViewModel 里抽掉，改由引擎的固定步长循环按真实帧间隔推进。

`game_viewmodel.py`：

```python
# 旧：依赖 time.time() 自搓 dt
def tick(self):
    if not self.state.running or self.state.paused:
        self._last_real_time = time.time(); return
    now = time.time(); dt = now - self._last_real_time; self._last_real_time = now
    self.state.elapsed += dt
    ...
    self._emit("tick")

# 新：dt 由循环注入，逻辑与帧率解耦
def tick(self, dt: float = 0.0):
    if not self.state.running or self.state.paused:
        return
    self.state.elapsed += dt
    if self.state.time_limit > 0 and self.state.elapsed >= self.state.time_limit:
        self.state.elapsed = self.state.time_limit
        self.state.lost = True; self.state.running = False
        self._emit("lose"); return
    self._emit("tick")
```
（删除 `__init__` 里的 `self._last_real_time` 与 `import time` 中仅用于计时的部分。）

`main.py`：

```python
import time
from allin_engine.core.game_loop import FixedTimestepLoop

class App:
    def __init__(self, root):
        ...
        self._loop = FixedTimestepLoop(self.vm.tick, fixed_dt=0.25)
        self._last = time.monotonic()
        self._tick_loop()

    def _tick_loop(self):
        now = time.monotonic()
        self._loop.advance(now - self._last)   # 内部按 0.25 切分，钳制单帧上限防死亡螺旋
        self._last = now
        self.root.after(250, self._tick_loop)
```

> 说明：对回合制消除游戏，`FixedTimestepLoop` 略"重"，但它是引擎的标准主循环范式，正好用来 dogfood；`fixed_dt=0.25` 保证每个 `after(250)` 恰好推进一次 `tick(0.25)`，行为等价于旧版但更稳健（卡顿时不漂移）。

---

## 4. 字体加载替换（`tile_renderer.py` + `hud.py`）

**`tile_renderer.py`** —— 删掉手写的 `_load_fonts` 路径搜索，改用引擎字体发现：

```python
from allin_engine.utils.font import discover_local_fonts

_FONT_TABLE = {alias: path for alias, path in discover_local_fonts()}

def _resolve(self, alias: str):
    return _FONT_TABLE.get(alias) or next(iter(_FONT_TABLE.values()), None)

def _font(self, size, symbol=False):
    path = self._resolve("arial" if symbol else "simhei")
    try: return ImageFont.truetype(path, size)
    except Exception: return ImageFont.load_default()
```

（SimHei/Arial 已复制到 `allin_engine/fonts/`，别名即 `simhei` / `arial`，被自动发现。）

**`hud.py`** —— 把硬编码 `("SimHei", 10)` 换成引擎 tkinter 字体：

```python
from allin_engine.utils.font import load_local_tk_font

self.f    = load_local_tk_font(10, name="simhei")
self.fb   = load_local_tk_font(11, name="simhei", bold=True)
self.fbig = load_local_tk_font(18, name="simhei", bold=True)
```
`load_local_tk_font` 返回 `tkinter.font.Font`，对 `Label(font=...)` 与 `Canvas(font=...)` 通用（`_flash_reject` 的 `font=self.fb` 直接可用）。

---

## 5. 迁移顺序（分步、每步可独立验证）

1. **嵌入**：robocopy 引擎副本（排除 .git）+ 复制 2 字体到 `fonts/`。
2. **字体**：改 `tile_renderer.py` + `hud.py`（纯 View 层，与逻辑无关，最安全）。
3. **事件**：改 `game_viewmodel.py` 接入 `EventBus`（保留 `add_listener`/`GameEvent`，视图零改动）。
4. **计时**：改 `game_viewmodel.tick(dt)` + `main.py`（`FixedTimestepLoop`）。
5. **收尾**：更新 `README.md`（标注引擎嵌入与替换点）+ 跑验证。

---

## 6. 验证方案

- **导入冒烟**（mahjong 目录）：
  ```bash
  python -c "import allin_engine; from allin_engine.core.event_bus import EventBus; from allin_engine.core.game_loop import FixedTimestepLoop; from allin_engine.utils.font import load_local_tk_font, discover_local_fonts; print('OK')"
  ```
- **无头逻辑测试**（托管 Python 即可，ViewModel 不依赖 tkinter）：
  用 `services.matcher.find_hint_pair` 反复找可消对并 `vm.select` 两次，直到清空或死局，断言：事件链路（`new_game`/`match`/`win`/`deadlock`）正常触发、无异常、`EventBus` 容错生效。
- **GUI 实跑**（本地 Python 3.14，含 tkinter，按惯例用它验证桌面端）：
  `python main.py` —— 验证渲染、字体、倒计时、提示/撤销/洗牌、模式切换。

---

## 7. 回滚方案（完全可逆）

mahjong 无 git，采用"改动前文件备份"：
- 改前把 4 个文件拷到 `D:\allin\right\mahjong\_refactor_backup\`（`main.py` / `game_viewmodel.py` / `tile_renderer.py` / `hud.py`）。
- 嵌入的 `allin_engine/` 是新增目录，删除即回退。
- 回滚 = 还原 4 文件 + 删 `allin_engine/` + 删 `fonts/` 复制的两字体。

---

## 8. 风险与应对

| 风险 | 应对 |
|---|---|
| `EventBus` 无通配订阅 | 用 `GAME_EVENTS` 枚举注册分发器，确定性规避 |
| 顶层 `import allin_engine` 触发 render（tkinter/pygame） | 已实测托管 Python 与本地 3.14 均可导入；无头测试用 3.14 跑（仅 import，不建窗） |
| 嵌入副本带引擎自带手写体 | 与 SimHei/Arial 并存，发现机制按别名区分，无冲突 |
| 改动破坏可玩性 | 领域逻辑零改动；每步独立验证；文件级备份可回滚 |

---

## 9. 明确的非目标（保持不动）

- `models/tile.py` `models/board.py` `models/game_state.py`
- `services/deck.py` `services/layouts.py` `services/matcher.py` `services/scorer.py`
- `views/board_canvas.py`（绘制/命中/动画逻辑）
- `views/tile_renderer.py` 的牌面绘制逻辑（仅字体加载方式换）
- `chess.py`（旧版 God Class，保留对比）
- 所有游戏规则、计分、布局坐标

---

## 10. 后续可选（本次不做）

- **深度 ECS 化**：把 144 张牌建模为 ECS 实体（`TileComponent` / `PositionComponent`），棋盘用 `World` 容器。收益对静态棋类存疑、回归风险高，留待单独评估。
- **存档接入**：用引擎 `systems.SaveLoadManager` 持久化棋局（当前无存档需求）。
- **音频接入**：用引擎 `audio` 合成消除/提示音效（需 pygame，属可选增强）。

---

**请你确认**：是否按上述方案执行？确认后我即从第 1 步（嵌入引擎）开始，逐文件落地并在每步跑验证。
