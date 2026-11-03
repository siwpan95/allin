# ADR-0006 —— 支柱清单以 yml 为唯一数据源推导（registry 为唯一代码边界）

- 状态：**accepted**（2026-11-04 落地：`kernel/tree.py` `_want_all_from_config()` + 导入期 fail-loud 校验；
  回归测试 `kernel/tests/test_kernel_want_all.py`）
- 相关：`kernel/registry.py`（SERVICES 封闭表）、`kernel/configs/cordis.allin.yml`、`kernel/tree.py`

## Problem

「四大支柱」这一份事实曾在**三处手抄**：`registry.py:SERVICES`、`tree.py:WANT_ALL`、
`cordis.allin.yml` 的 entry 清单。yml 头注释自称「改一行 yml 即可换装配，不改代码」，
但实际受 entry 白名单（`tree.py:ALLOWED_NAME_*`）+ `SERVICES` 映射 + `WANT_ALL` 就绪等待
三重钉死——新增第五支柱要改 3 个文件，且任何一处漏改都**没有报警**（2026-11-04 工程审查 A1）。

## Decision

- `WANT_ALL` **从 yml 的 entry id 推导**（`_want_all_from_config()`），不再手抄；
- 导入期 fail-loud 校验 `ids ⊆ registry.SERVICES`：yml 写了白名单外的短名 = `import kernel.tree`
  即报错并点名越界 id 与允许集，而不是挂载时才炸；
- `registry.py` 仍是**唯一代码边界**（封闭白名单防「配置即代码」任意 import，不变）；
- yml 保留 config 数据职能，头注释改写为真实语义（不再是"改一行换装配"的表面叙事）。

## Consequences

- 新增第五支柱 = registry.py（边界）+ services/（实现）+ yml（数据），共 3 处——
  其中数据 1 处改动此前也会让 WANT_ALL 漂移，现在自动跟随；
- 「yml 单独改坏」从隐性不一致变成启动红灯（符合全仓 fail-loud 纪律）；
- 配置缺席（`ALLIN_CONFIGS` 指向空目录）时退回出厂四支柱口径，不阻断新装环境。
