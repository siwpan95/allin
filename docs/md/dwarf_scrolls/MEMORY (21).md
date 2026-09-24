# dwarf_scrolls 项目长期笔记

## 架构铁律（勿违）
- **`dwarf_scrolls/allin_engine/` 是项目的「内置引擎地基」，不是死副本、不是冗余。**
  首轮评估曾误判其为"23k 行死副本"建议删除——此结论已作废。全哥明确：
  引擎副本 = 复制即复用 + 零项目外耦合的活化地基，整项目 `import allin_engine` 解析到 `dwarf_scrolls/allin_engine`。
  **任何时候都不要把这些引擎文件当冗余/死代码删除或移走。**
- 自包含验证法：`core/engine_bootstrap.py` 把 `GAME_ROOT`(dwarf_scrolls) 注入 sys.path 最前。
  硬隔离测试 = 临时移走外部 `D:\allin\allin_engine`，确认 `import allin_engine` 仍解析到内部副本。
- 运行：`cd D:/allin && python -m dwarf_scrolls.game.main`（入口在根 `main.py` 的 `Game`/`main()`，`game/main.py` 仅零复制桥接 re-export）。
- 引擎测试：从 `dwarf_scrolls` 目录 `python allin_engine/test/run_all.py`（309 项）；单文件 `python -m pytest allin_engine/test/test_X.py -q`。
- `pyproject.toml` 无 `dwarf-scrolls-test` 控制台脚本（run_all 用顶层 `import allin_engine`，控制台入口路径冲突，坏）。
