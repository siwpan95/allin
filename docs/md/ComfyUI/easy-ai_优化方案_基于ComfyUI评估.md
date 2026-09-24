# easy-ai 优化方案 —— 基于 ComfyUI 评估

> 评估时间：2026-07-05 | easy-ai v3.1.0 vs ComfyUI v0.27.0

---

## 零、先比差距：easy-ai vs ComfyUI 对比

| 维度 | easy-ai | ComfyUI | 谁更好 |
|---|---|---|---|
| Python 文件数 | 52 | ~590 | — |
| 最大文件行数 | 766 (main.py) | 2570 (nodes.py) | ✅ easy-ai |
| 裸 except | 2 处 | 50+ 处 | ✅ easy-ai |
| TODO 债务 | 0 处 | ~200 处 | ✅ easy-ai |
| 测试文件比 | 3/52 ≈ 5.8% | 98/590 ≈ 16.6% | ComfyUI 量多 |
| 类型注解 | 有，但偏宽泛 | 精确 `Literal` 类型 | ComfyUI |
| 插件架构 | 手动列表 | 自动注册表 | ComfyUI |
| 缓存策略 | 无 | 4 种策略 | ComfyUI |
| API 版本化 | 无 | 三级渐进式 | ComfyUI |
| Docstring | ✅ 模块/类级完整 | ❌ 大段禁用 lint | ✅ easy-ai |

**结论：easy-ai 的代码规范比 ComfyUI 好，ComfyUI 的工程抽象比 easy-ai 深。优化方向是：保持规范，引入 ComfyUI 的成熟工程模式。**

---

## 一、最高优先级：匹配器注册表 → 对标 NODE_CLASS_MAPPINGS

### 现状

`ai/pipeline.py` 第 81-91 行，匹配器写死在 `_init_matchers()` 里：

```python
def _init_matchers(self) -> List[BaseMatcher]:
    if matcher_config.get("regex", {}).get("enabled", True):
        instances.append(RegexMatcher(matcher_config.get("regex", {})))
    if matcher_config.get("fuzzy", {}).get("enabled", True):
        instances.append(FuzzyMatcher(matcher_config.get("fuzzy", {})))
    if matcher_config.get("markov", {}).get("enabled", False):
        instances.append(MarkovMatcher(matcher_config.get("markov", {})))
```

添加新匹配器 = 改源码 + 改配置 JSON。不符合「零硬编码」设计目标。

### ComfyUI 怎么做

```python
# comfyui 的 nodes.py
NODE_CLASS_MAPPINGS = {}  # 全局注册表

# 每个节点模块在文件末尾自动注册：
NODE_CLASS_MAPPINGS["KSampler"] = KSampler
NODE_CLASS_MAPPINGS["CLIPTextEncode"] = CLIPTextEncode
```

任何第三方 `custom_nodes/` 目录下的 Python 文件都可以把自己的类注册进来，**无需改核心代码**。

### 优化方案

```python
# ai/matchers/registry.py（新增）
from typing import Dict, Type
from .base import BaseMatcher

MATCHER_REGISTRY: Dict[str, Type[BaseMatcher]] = {}

def register_matcher(name: str):
    """装饰器：将匹配器类注册到全局表。"""
    def decorator(cls):
        MATCHER_REGISTRY[name] = cls
        return cls
    return decorator

# ai/matchers/regex_matcher.py
from .registry import register_matcher

@register_matcher("regex")
class RegexMatcher(BaseMatcher):
    ...

# ai/matchers/fuzzy_matcher.py
@register_matcher("fuzzy")
class FuzzyMatcher(BaseMatcher):
    ...

# ai/pipeline.py —— 替换 _init_matchers
def _init_matchers(self) -> List[BaseMatcher]:
    config = self.config.get_matchers()
    instances = []
    for name, cls in MATCHER_REGISTRY.items():
        if config.get(name, {}).get("enabled", True):
            instances.append(cls(config.get(name, {})))
    instances.sort(key=lambda m: m.priority)
    return instances
```

**收益：**
- 添加新匹配器 = 写类 + 加装饰器 + 改 JSON，不改 pipeline
- 第三方可以 `from easy_ai.matchers.registry import register_matcher` 注入自己的匹配器
- 与 ComfyUI 的 custom_nodes 插件系统完全同构

---

## 二、响应器同理：注册表化

### 现状

`pipeline.py` 第 93-106 行，响应器也是硬编码 if/elif 链。

### 优化方案

```python
# ai/responders/registry.py
RESPONDER_REGISTRY: Dict[str, Callable] = {}

@register_responder("time")
class TimeResponder:
    ...
```

效果完全同匹配器注册表。新增响应器零改 pipeline。

---

## 三、管道从线性 → DAG 对标 ComfyUI 执行图

### 现状

`pipeline.py` 的 `process()` 是严格线性的：

```
空输入 → 安全过滤 → 响应器 → 记忆匹配 → 匹配器竞争 → 兜底
```

每个请求必须走完整条链，无法跳过或并行。

### ComfyUI 怎么做

```python
# comfy_execution/graph.py
class DynamicPrompt:
    """DAG 执行图：拓扑排序 + 惰性求值 + 条件分支"""
    def get_node(self, node_id): ...
    def add_ephemeral_node(self, ...): ...  # 运行时动态插入节点
```

每个「节点」有明确的输入/输出类型，执行引擎按依赖关系决定执行顺序。不依赖的节点直接跳过。

### 优化方案：Pipeline v2 — 可配置 DAG

```python
# ai/pipeline_v2.py（新增，渐进替换）
from dataclasses import dataclass
from typing import Dict, List, Set

@dataclass
class PipelineNode:
    name: str
    fn: Callable
    requires: List[str] = field(default_factory=list)  # 依赖的前置节点
    provides: List[str] = field(default_factory=list)   # 产出的能力标签
    enabled: bool = True

class DAGPipeline:
    def __init__(self, nodes: List[PipelineNode]):
        self.nodes = {n.name: n for n in nodes}
        self._exec_order = self._topo_sort()
    
    def _topo_sort(self) -> List[str]:
        """拓扑排序：确保依赖的节点先执行。"""
        ...
    
    def run(self, input_data: dict) -> dict:
        """按拓扑序执行，有缓存就跳过。"""
        context = {**input_data}
        for name in self._exec_order:
            node = self.nodes[name]
            if not node.enabled:
                continue
            if self._can_skip(name, context):
                continue
            context = node.fn(context) or context
        return context
```

**收益：**
- 管道不再是一条直线，而是一个可配置的 DAG
- 条件分支、并行执行成为可能
- 第三方模块可以插入自己的节点到管道任意位置

---

## 四、响应缓存 → 对标 ComfyUI 多策略缓存

### 现状

easy-ai 每次请求都做完整的匹配器链计算。对于「今天几号」这种高频确定性查询，每次都重新计算。

### ComfyUI 怎么做

```python
# comfy_execution/caching.py
class BasicCache: ...
class LRUCache: ...
class RAMPressureCache: ...
class NullCache: ...

# 执行引擎用 CacheType 枚举选策略
class CacheType(Enum):
    CLASSIC = 0
    LRU = 1
    NONE = 2
    RAM_PRESSURE = 3
```

### 优化方案

```python
# ai/cache.py（新增）
from abc import ABC, abstractmethod
from typing import Optional, Any

class ResponseCache(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[str]: ...
    @abstractmethod
    def put(self, key: str, value: str): ...

class LRUResponseCache(ResponseCache):
    def __init__(self, max_size: int = 1000):
        self._cache = OrderedDict()
        self._max_size = max_size
    def get(self, key): ...
    def put(self, key, value): ...

class TTLResponseCache(ResponseCache):
    """带过期时间的缓存，适合'今天几号'类查询。"""
    def __init__(self, ttl_seconds: int = 60): ...

class NoCache(ResponseCache):
    """关闭缓存（默认）。"""
    def get(self, key): return None
    def put(self, key, value): pass
```

在 `AICore.respond()` 中插入缓存层：

```python
def respond(self, message: str, session_id=None) -> str:
    # 新增：先查缓存
    cached = self._cache.get(message)
    if cached:
        return cached
    
    reply = self.pipeline.process(message, ...)
    
    # 新增：写入缓存
    self._cache.put(message, reply)
    return reply
```

---

## 五、配置 Schema 校验 → 对标 ComfyUI comfy_config

### 现状

`config_loader.py` 的校验很弱，只是检查 `rules` 字段存在。JSON 中的拼写错误静默忽略。

### ComfyUI 怎么做

```python
# comfy_config/types.py — 强类型配置定义
class ConfigModel(BaseModel):
    ...
```

虽然 ComfyUI 没有完整使用 Pydantic，但有独立的配置类型文件。

### 优化方案

```python
# ai/config_schema.py（新增）
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class RuleConfig:
    pattern: str
    responses: List[str]
    confidence: float = 0.5
    source: str = "rule"
    
@dataclass
class AIConfig:
    name: str = "easy-ai"
    version: str = "3.0"
    empty_input_response: str = "请说点什么吧。"
    fallback_response: str = "我不太明白。"
    rules: List[RuleConfig] = field(default_factory=list)
    matchers: dict = field(default_factory=dict)
    responders: dict = field(default_factory=dict)

# config_loader.py 中增加 validate()
def validate(self) -> List[str]:
    errors = []
    for i, rule in enumerate(self.data.get("rules", [])):
        if "pattern" not in rule:
            errors.append(f"规则 #{i} 缺少 pattern")
        if "responses" not in rule:
            errors.append(f"规则 #{i} 缺少 responses")
    return errors
```

---

## 六、进度回调 → 对标 ComfyUI ProgressHook

### 现状

当 `AICore.respond()` 处理复杂查询时，调用方（如 GUI）无法知道进度。用户感觉卡住了。

### ComfyUI 怎么做

```python
# main.py
def hijack_progress(server_instance):
    def hook(value, total, preview_image, prompt_id=None, node_id=None):
        progress = {"value": value, "max": total, ...}
        server_instance.send_sync("progress", progress, client_id)
    comfy.utils.set_progress_bar_global_hook(hook)
```

### 优化方案

```python
# ai/core.py — 增加回调支持
class AICore:
    def __init__(self, ..., on_progress: Optional[Callable] = None):
        self.on_progress = on_progress
    
    def respond(self, message, ...) -> str:
        self._emit_progress("安全过滤", 0, 5)
        # ... 安全过滤 ...
        
        self._emit_progress("响应器", 1, 5)
        # ... 响应器 ...
        
        self._emit_progress("记忆匹配", 2, 5)
        # ...
        
        self._emit_progress("匹配器", 3, 5)
        # ...
        
        self._emit_progress("完成", 5, 5)
        return reply
    
    def _emit_progress(self, stage: str, step: int, total: int):
        if self.on_progress:
            self.on_progress(stage, step, total)

# GUI 使用
def on_progress(stage, step, total):
    status_bar.set(f"{stage} ({step}/{total})")

ai = AICore(on_progress=on_progress)
```

---

## 七、版本化配置 Schema → 对标 ComfyUI API 版本

### 现状

配置文件 `config/default.json` 和 `config/ai_knowledge.json` 没有版本号。改了 schema 之后，老文件会默默出 bug。

### ComfyUI 怎么做

```python
# comfy_api/version_list.py
# comfy_api/v0_0_1/    ← 旧 API
# comfy_api/v0_0_2/    ← 新 API
# comfy_api/latest/    ← 最新 API（符号链接思想）
```

三级渐进式 API，老客户端用老 API 不受影响。

### 优化方案

```json
// config/default.json v3
{
    "schema_version": "3.0",
    "name": "easy-ai",
    "rules": [...]
}
```

```python
# config_loader.py
SCHEMA_MIGRATIONS = {
    "1.0": migrate_1_to_2,
    "2.0": migrate_2_to_3,
}

def load(self, path: str):
    data = json.load(open(path))
    version = data.get("schema_version", "1.0")
    while version in SCHEMA_MIGRATIONS:
        data = SCHEMA_MIGRATIONS[version](data)
        version = data["schema_version"]
    self.data = data
```

---

## 八、简单修复：消除最后的裸 except

```python
# trpg/paotuan_gui.py — 唯一的 2 处裸 except
# 当前：
try:
    ...
except:
    pass

# 修复为：
try:
    ...
except (ValueError, KeyError, OSError) as e:
    logger.warning("paotuan_gui 错误：%s", e)
```

---

## 九、简单修复：main.py 子命令拆分

`main.py` 目前 766 行，是所有文件中最大的。对标 ComfyUI 的做法（`server.py` 独立于 `main.py`），把各个子命令移到独立模块：

```
main.py           # 150 行：只负责参数解析 + 调度
commands/
  chat_cmd.py     # 100 行
  story_cmd.py    # 120 行
  paotuan_cmd.py  # 50 行
  trpg_cmd.py     # 80 行
  train_cmd.py    # 60 行
  ... 
```

---

## 十、优化优先级排序

| 优先级 | 任务 | 改动量 | 收益 | 对标 ComfyUI 的哪部分 |
|---|---|---|---|---|
| 🔴 P0 | 匹配器注册表 | 小（新增1文件+改2行） | 大 | `NODE_CLASS_MAPPINGS` |
| 🔴 P0 | 响应器注册表 | 小（新增1文件+改1行） | 大 | 同上 |
| 🟡 P1 | 响应缓存 | 中（新增1文件） | 中 | `comfy_execution/caching.py` |
| 🟡 P1 | 进度回调 | 中（改 `respond()` + 新增回调） | 中 | `hijack_progress()` |
| 🟡 P1 | 配置 Schema 版本化 | 中（改 config_loader） | 中 | `comfy_api/version_list.py` |
| 🟢 P2 | 管道 DAG 化 | 大（新增 pipeline_v2） | 大 | `comfy_execution/graph.py` |
| 🟢 P2 | main.py 拆分 | 中（新建 commands/ 目录） | 小 | ComfyUI 的模块化 |
| 🟢 P2 | 消除裸 except | 小（改 2 行） | 小 | — |
| 🟢 P2 | 配置校验增强 | 小（新增 validate 方法） | 小 | `comfy_config/types.py` |

---

## 十一、不应该从 ComfyUI 学的东西

| ComfyUI 的坏习惯 | 为什么不要学 | easy-ai 现在怎么样 |
|---|---|---|
| 2000+ 行单文件 | 难以维护、review、测试 | ✅ 最大 766 行，保持 |
| 裸 except 满天飞 | 吞掉 KeyboardInterrupt | ✅ 只有 2 处，修掉就好 |
| 禁掉 lint 规则假装没问题 | 自欺欺人 | ✅ 不要引入 pylint，不需要 |
| 全局可变状态（module 级变量） | 多线程隐患 | ✅ 绝大多数状态在类实例里 |
| 大段代码放 `__init__.py` | 语义混乱 | ✅ `__init__.py` 都很干净 |

---

## 十二、总结

easy-ai 的根基比 ComfyUI 干净得多——代码规范、文件大小、docstring、TODO 债务全面优于后者。优化方向不是「重写」，而是「在干净的基础上引入更好的工程抽象」：

1. **注册表模式**（P0）：让匹配器/响应器像 ComfyUI 的 custom_nodes 一样可插拔
2. **响应缓存**（P1）：高频查询不用每回重算
3. **进度回调**（P1）：GUI 不再傻等
4. **管道 DAG 化**（P2 远期）：最大的架构升级，对标 ComfyUI 执行图

这些改进全部向后兼容，渐进式替换，不破坏现有功能。
