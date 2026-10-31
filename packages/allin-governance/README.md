# allin-governance

把 **allin 治理中枢** 里本来就通用的部分装成一个可安装件 —— 让外部的人能直接消费，
而不是先读 86 份文档。

```bash
pip install allin-governance

allin-governance --version
allin-governance repocheck <目录>          # 离线仓库体检
allin-governance repocheck --help
```

## 它解决什么

一个人管多个仓库时，塌方的不是代码能力，而是这几件事：

| 塌方 | 现实表现 |
| --- | --- |
| 事实源分裂 | 同一件事在 README、文档、聊天记录里各有一版 |
| 假绿 | 验证脚本打印了 `PASS`，但退出码是 0 |
| 门禁靠自觉 | 「记得别写死路径」—— 没有可执行的门禁等于没有约束 |
| AI 放大错误 | 一次错口径被高速复制到几十个仓 |

所以这套东西的取向是：**给人看的规矩变成给机器跑的门禁，给机器跑的门禁要有给人看的账。**

## 用法（Usage）

```bash
# 体检当前目录（最常用）
allin-governance repocheck .

# 体检一个发布区（每个仓一个项目）
allin-governance repocheck <发布区>

# 进 CI：有 error 级问题即非 0 退出
allin-governance repocheck . --fail-on error

# 其他常用开关
allin-governance repocheck . --format json --output report.json
allin-governance repocheck . --skip-rules 1,7        # 临时豁免误报
allin-governance repocheck --dump-profile            # 列出全部 30 条规则（不扫描）
```

### 示例输出

```text
根目录：.
发现项目数：2
健康分：均值 6.0 / 最低 6.0　通过率 100%

== kernel  (kernel)  健康分 6.0
   ✓ 无达到阈值的问题
   (跳过 10 项：no-dotgit, no-workflow, user)
```

## 当前能力

### `repocheck` —— 离线仓库体检

**30 条规则**，给出 0–10 健康分与 `error` / `warn` / `info` 三级问题；
支持 text / JSON / CSV / HTML 四种导出。

```bash
allin-governance repocheck .                    # 体检当前目录
allin-governance repocheck <发布区>             # 体检一个发布区
allin-governance repocheck . --fail-on error    # 进 CI：有 error 级问题就失败
```

三条硬性质（不是宣传语，是设计约束）：

- **离线只读** —— 不联网、不执行被体检的代码，只看文件与 git 元数据。
- **零第三方依赖** —— 只用标准库。装了 `full` 附加依赖会用更严格的库做二次校验，
  不装则走内置实现，**结论口径一致**。
- **退出码如实** —— 体检结论全在退出码上，包装层不改写它。

## 与 allin 仓的关系

本包的 `repocheck` **源码只有一份**：真身在
[`allin`](https://gitee.com/siwpan/allin) 仓的 `tools/repocheck/`，
打包时由 `pyproject.toml` 的 `package-dir` 映射进来，**不复制**。
理由很实际：两份代码必然漂移，而判断哪份是准的成本，远高于省下的打包麻烦。

## 安装

```bash
pip install allin-governance            # 核心（零依赖）
pip install allin-governance[full]      # 加严格校验的附加依赖
```

要求 Python ≥ 3.11。

## 许可

**MIT-0**（MIT No Attribution）—— 与 allin 仓根一致。

## 状态

`0.0.0a0` 是**占位版本**，只用于先占住 `allin-governance` 这个名字。
正式形态仍在演进，见 allin 仓的
[`REC-AU-21`](https://gitee.com/siwpan/allin/blob/master/docs/记录/审计/allin自身做大做强方向修正_2026-10-31.md)。
