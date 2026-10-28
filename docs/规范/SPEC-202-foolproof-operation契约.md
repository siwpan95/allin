# SPEC-202 · foolproof-operation 契约

> **编号** SPEC-202 ｜ **效力** 准则（单仓契约） ｜ **状态** 生效
> **生效** 2026-09-23 ｜ **最后修订** 2026-10-28 ｜ **适用面** `/repos/foolproof-operation` 一仓
> **承载体** `python -m unittest discover` 271/271、`ResourceWarning=error`、CLI 全子命令 exit 0；与 SPEC-004 §20–23 互锁
> **引用格式** SPEC-202 §黄金值

---

## foolproof-operation：Cordis 内核 + USN 索引（2026-09-23，阶段 0~6 完成并**已推送发布**）

- **本仓现状（接手先看这行）**：`/repos/foolproof-operation`（siwpan，master，
  本地=远端=`41b320a`，tag `v1.1.0`，gitee release id `1162143`（附件 3255007 = 便携 zip 14MB）；
  2026-09-23 完成「Cordis 式可逆插件内核 + 自研 NTFS USN/MFT 索引」重构，三个提交
  `e8f1086`（内核+索引）/ `e0dd51b`（插件接线）/ `41b320a`（运维+打包+文档）已推送，工作区干净。
  规划与阶段表见 `/allin/docs/md/allin主工作区/USN索引与Cordis内核规划_2026-09-23.md`（**其阶段勾选即事实源**）。
- **结构**：`core/`（Context/effect 逆序回滚/fork/isolate/事务化清单装配 + runtime/tasklog/audit）、
  `index/`（只读 USN 客户端 / FRN 路径还原 / SQLite 按卷分库 / 索引服务 / 基准探针）、
  `plugins/`（categories·pip·reqtxt·installer·search·scanner）、`foolproof.composition.json`（10 行清单）、
  `tests/`（271 例）、`foolproof-operation/docs/usn-indexer.md`（原理/实测/踩坑）。
- **黄金值（不设环境变量）**：`python -m unittest discover` 271/271；`ResourceWarning=error` 亦全绿；
  CLI 子命令 list/scan/envs/doctor/tasks/check/es 全 exit 0；`smoke_test.py` GUI 冒烟无 Traceback；
  便携 exe（`requirements.spec`）`list/doctor/envs` exit 0。
- **关键实测**：全盘 479 万条记录建库 ≈50s；查询 0.02~1.46ms；环境发现 **4 → 208 候选**。
- **两条口径纪律（本仓特有）**：① 索引只读——**绝不调用** `FSCTL_CREATE_USN_JOURNAL`（改卷状态的写操作）；
  ② 全量枚举必须 `LowUsn=0`（用 journal 的 `FirstUsn` 只能拿窗口内记录且不报错）。
- 相关铁律见本文档调试铁律 20~23（`$args` 形参、SQLite `IN COLLATE` 全表扫描、
  `ResourceWarning=error` 抓资源泄漏、测试断言禁子串启发式）。

