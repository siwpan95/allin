# 贡献指南

## 提 issue

- 报 bug 请附上：`python main.py --dump-profile` 的输出、`repocheck --version`、
  Python 版本、以及触发问题的目录结构（可脱敏）。
- 讨论新规则时请说明：它检查什么、**只读本地文件能否判定**、建议的严重度。
  需要联网才能判定的项不在本项目的范围内。

## 提 pull request

1. Fork 并新建分支，分支名建议 `feat/rule-xx` 或 `fix/yy`；
2. 先跑通现有测试：

   ```bash
   python -m pytest test_scanner.py -q
   ```

3. 新增规则的改动范围（**规则即数据**，不需要动控制流）：

   | 位置 | 改什么 |
   | --- | --- |
   | `rules_*.py` | 追加一个 `Rule(...)` 与对应的 `_check_*` 函数 |
   | `README.md` | 规则表加一行 |
   | `test_scanner.py` | 加一条断言，最好用 `test_fixtures.good()` 做减法 |

4. 规则 id **只增不改号**（`--skip-rules` 与外部 Agent 按 id 引用）；
5. 提交前自检一遍：`python main.py . --fail-on error` 应当退出码为 0。

## 代码约定

- 运行时**保持零第三方依赖**。需要专业库时按 `_optional.py` 的能力探测方式接入，
  并同时提供标准库降级实现（两者结论口径必须一致）。
- 注释与文档用中文；变量与函数名用英文。
- 不要为单条规则新增独立的 git 调用 —— 复用 `ProjectContext.git` 的缓存。
- 新增会遍历全仓的逻辑，必须带上文件数或字节数上限，并在触顶时标 `degraded`。

## 许可

贡献的代码默认以 [MIT](LICENSE) 许可发布。
