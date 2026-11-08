<!--
四条约定，别的都是细节。阅读约 40 秒。
-->

## 这个 PR 做了什么

<!-- 一句话。如果你需要三句才能说清，它可能该拆成三个 PR。 -->

## 类型

- [ ] 修 bug（哪个 issue：# ）
- [ ] 改判据（哪道门禁：`g__-____`）
- [ ] 文档
- [ ] 其他：

## 四条约定（请逐条确认）

- [ ] **只做一件事。** 混着改的 PR 我没法复核。
- [ ] **改了判据就改了自检。** 动了 `gates/*.py` 的 PR，`--selfcheck` 必须仍满足 `caught ≥ 1`、`misreports == 0`。
- [ ] **没有直接改快照文件。** `tools/gate/governance/` 是生成物，下次 `init --force` 会覆盖；要长期保留请做成独立的新门禁（新 id + 新脚本 + 注册 + 写进 `RULES.md`）。
- [ ] **UTF-8 + LF。** 仓库有 `.gitattributes` 钉着，别绕过。

## 你跑过什么

```bash
bash scripts/bootstrap.sh
bash scripts/run_all_gates.sh
```

机器可读汇总行（`bash scripts/run_all_gates.sh` 会打印，复制整行）：

```text
ALLIN_GATE_SUMMARY status=clean fail=0 skips=0
```

> 判据：**`status=clean`**（`fail=0` 且 `skips=0`）才算干净。
> `status=incomplete`（含 SKIP）**不是通过** —— SKIP 是「没检查」，见 `.github/workflows/gates.yml` 的「SKIP ≠ pass」；
> 旧口径「全部门禁通过。」在含 SKIP 时仍会打印，已不再作为准出凭据。
> `status=failed` 一律先修。**没有贴这一行、或 status 非 clean 的 PR 我会先自己跑一遍再谈内容** ——
> 不是因为不信任，而是因为这套东西的可信度完全建立在"跑过"上。
> 若能附上对应 CI run URL（GitHub Actions / Gitee Go），复核会更快。
