---
name: cordis-v4-integration
description: 把 Cordis v4.0.0（Python 移植 geohotstan/cordis-py）落地进项目的可复用范式——共同核即服务 / inject 依赖自动排序 / fiber 可逆副作用（GL 等资源回滚）/ cordis.yml 配置树（Loader/EntryTree）/「demo 与 headless 验证共用一条挂载路径」。含四个硬坑（_isolate KeyError、entry 需 default=Service、plugin-group 子服务对根 ctx 不可见、顶层名双模块副本）与离线锁 commit 取证法。触发词：cordis 配置树、cordis.yml、Loader、EntryTree、_isolate KeyError、cordis inject 服务、vendor cordis、fiber dispose 回滚、mount_tree、cordis-py 锁 commit。
agent_created: true
---

# Cordis v4.0.0（Python）项目落地

参考实现（本机）：`G:/repos/3dworld/experiments/cordis/`——试点一~三 + 转正全部收口，可直接对照抄：
`tree_boot.py`（配置树引导）、`services/*`（entry 适配层）、`config_boot.py`（headless 验证）、
两个 `cordis.*.yml`。其他 Cordis 相关项目：image-scraper（多源爬虫）、DeepSeek Harness（dsh）。

## 0. 定位与安装

- 上游：`github.com/geohotstan/cordis-py`（MIT；**import 名 `cordis`**）。
  ⚠️ 别和 PyPI 的 `cordis-python`（import `cordis_py`）混淆——是另一个移植。
- vendor 进仓库：`vendor/cordis/` 原样保留 src-layout；给项目 venv 挂 `.pth`（内容一行
  `<repo>/vendor/cordis/src`）→ 任意代码直接 `import cordis`。换环境兜底：`CORDIS_SRC` 环境变量。
- 硬依赖：`pyyaml`（`include.py` 顶部 import）、`watchdog`（hmr），必须装进同一 venv。

## 1. 服务与插件（v4.0.0 实跑形态）

```python
from cordis import Context, Service

class RenderService(Service):
    def __init__(self, ctx, config):         # config ← cordis.yml 的 config 字段
        super().__init__(ctx, "render")      # 第二参 = 服务名（之后 ctx.render 属性可访问）
        ...
    def __cordis_init__(self):               # 初始化钩子；可 return None / disposer
        ...
        return None

class MyKernel(Service):
    inject = ['render', 'entity', 'economy', 'rules']   # 依赖自动排序，无需手工编排
```

- 服务一律经 `ctx.<服务名>` **属性**访问（`ctx.render.live_count()`）。
- `await ctx.plugin(Loader)` 返回的是 **Fiber**；实例在 `ctx.loader`（别用返回值当实例用）。

## 2. 可逆副作用 = 资源回滚（GL / 音频等）

```python
for h in handles:
    def release(h=h):
        return lambda: render.release(h)     # 返回 disposer 的 callable（或 yield disposer 的 generator）
    self.ctx.effect(release)
# 卸载：await kernel.ctx.fiber.dispose() —— 所有 effect 按 LIFO 回滚
```

验收断言（headless 也成立）：`live_count() -> 0` 且 `released == acquired`。

## 3. cordis.yml 配置树（全部要点）

```yaml
- name: pkg.services.economy     # importlib 模块路径；模块须写一行：default = EconomyService
  id: economy
  config: { gold: 300 }          # 透传给 __init__(ctx, config)
```

引导四步（缺一不可）：

```python
await ctx.plugin(Loader)                    # ① 先挂 Loader
loader = ctx.loader                         # ② 实例在 ctx.loader
for _ in range(16):                         # ③ drain 事件循环！
    await asyncio.sleep(0)                  #    等 isolate 子插件注册 loader/entry-init
await loader.root.update(yaml.safe_load(f)) # ④ 声明即挂载（按 inject 依赖图排序）
```

**五个硬坑（都真实踩过）**：

1. 不做 ③ 的 drain → 首条 entry 建好时抛 `KeyError: '_isolate'`（isolate 由 Loader 自动注册，晚一步）。
2. entry 的 `name` 解析为模块后取 `module.default`——**模块必须导出 `default = <Service类>`**
   （惯用法：`services/xxx.py` 一行适配 `from pkg.kernel import X; default = X`）。
3. **嵌套 `@cordisjs/plugin-group` 会让子服务对根 ctx 不可见**（`ctx.render is None`）→
   用**扁平 entry 列表**最稳；需要分组语义时再评估。
4. 跨模块 import 一律用**包路径**（`from pkg.kernel_a import X`）；用顶层名（`from kernel_a import X`）
   会让同一文件被加载成两份模块对象（双副本，identity 检查时阴魂不散）。
5. **Service 里不要写 `@staticmethod`**：`Traceable` 代理对**任何**方法都注入 self
   （`func(self_ref._shadow_self(), *args, **kwargs)`），于是 `self._helper(a, b)` 会给静态
   方法多塞一个 self → `TypeError: takes 3 positional arguments but 4 were given`；
   辅助方法一律写成实例方法（迷宫内核的 `_open_neighbors` 就是这么翻的车）。

## 4. 验证范式：「demo 怎么挂的 = 验证怎么挂的」

- 抽 `mount_tree(path, want)`（新建 Context → load_tree → 就绪轮询）作**唯一挂载入口**；
  应用的 `_mount_kernel` 与 headless 验证脚本调**同一函数、同一 `want` 列表**——不存在两套接线。
- 就绪判据：`want` 服务全部可达 **且** `render.live_count() > 0`（内核 GL 句柄已取得）。
- headless 验证加「配置传递断言」：yaml 声明值必须到达服务，且与内核默认值一致（防配置树漂移）。
- 排查：报 `缺失服务` 时先看 want 全不全；`sys.modules` 里查有没有顶层名双副本。
- **服务为 None 却一条日志都没有**（最常见的"静默失败"）= `__cordis_init__` 抛异常被 fiber 吞了：
  在已挂好的 ctx 上手动 `await ctx.plugin(MyKernel)` 一次，traceback 会直接打出来。
- 调试脚本模板：`ctx=Context(); loader=await load_tree(ctx, cfg); [await asyncio.sleep(0) for _ in range(40)]; await loader.await_()`
  然后逐个 `print(n, getattr(ctx, n, None))`，看哪个服务没起来。

## 5. 锁 commit + 记账（vendor 转正三件套）

```sh
unzip -z  cordis-py-main.zip     # ★ 直接证据：GitHub 归档 zip 的 comment 字段 = commit SHA（离线可复核！）
unzip -l  cordis-py-main.zip     # 内容指纹（如按新目录特征核对 commit）
sha256sum cordis-py-main.zip     # zip 整体指纹
```

- **`unzip -z` 那一行就是 commit SHA**——GitHub「Download ZIP」虽无 `.git`，但归档 zip 的 comment
  即 commit，无需联网/无 TLS 也能钉死。
- 联网兜底：`git ls-remote` 被 TLS 拦时，用 WebFetch 读 `github.com/<repo>/commits/<branch>` 页。
- 记账：`VENDOR.md`（来源 + 许可 + 借用 API 范围）+ `cordis.lock`（commit / sha256 / 复核命令）。

## 6. 自检清单

- [ ] `import cordis` 成功（.pth 或 `CORDIS_SRC`），`pyyaml`/`watchdog` 已装
- [ ] 配置树 headless 跑通：`*_OK` + 配置传递断言 + 回滚断言
- [ ] `sys.modules` 无顶层名双副本
- [ ] `VENDOR.md` / `cordis.lock` 与上游 commit 一致（`unzip -z` 复核）
