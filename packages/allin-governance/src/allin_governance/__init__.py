"""allin-governance —— 工作区治理中枢的可安装出口。

**这个包是什么**：把 `allin` 治理仓里那些**本来就通用**的部分装成一个可安装件，
让「外部的人」能直接消费，而不是读 86 份文档。

它当前提供：

* `repocheck` —— 离线仓库体检，30 条规则，零第三方依赖。
  真身在仓内 `tools/repocheck/`，本包打包时映射进来（**源码只有一份**）。
* `init` —— 在一个空目录里生成**可跑的最小治理骨架**：14 道门禁 + 文档四分类
  + registry + 基线棘轮。跑完 `npm run check:governance` 就是绿的（实测）。

设计取向（与 REC-AU-21 的方向一致）：
* 治理工具必须**能在什么都没装的机器上跑** —— 所以运行时零第三方依赖；
* 判据必须**可复跑** —— 所以它是离线只读、不联网、不执行被测代码；
* 一个发布面，多个子命令 —— 所以 `repocheck` 是子命令而不是独立包。

    $ allin-governance --version
    $ allin-governance repocheck <目录>
"""

from __future__ import annotations

__all__ = ["__version__"]

#: 与 pyproject 的 project.version 保持一致 —— **单一来源是 pyproject**，
#: 这里只是运行期读得到的那一份；`tests/test_cli.py` 逐次对账，两处不许对不上。
#:
#: 版本史（可复述的差异，不是流水账）：
#:   0.0.0a0–a10 占位系列：占名 → 修 cp1252 崩溃 → 自包含 sdist → 补 4 份事实源
#:               → profile 预设 → 工具随包分发 → 嵌套子包/双环境 import 修复。
#:   1.0.0        第一个正式版，冻结五个子命令名与 0/1/2/3 退出码语义。
#:                **该版 sdist 装不上**（跨目录映射未物化，见 docs/记录/事故/）。
#:   1.0.1        同日另一条工作线发布：物化 sdist（可安装）+ 新增 `github` 子命令与
#:                `_github` 包映射；**不含**本线的 verify 越界防线 / SPDX 元数据 / 回归测试。
#:   1.0.2        本线收口：`verify` 拒绝越界清单、license 改 SPDX、新增 release_preflight
#:                与 sdist 自包含回归测试、版本护栏改单一来源。
#:   1.0.3        新增第 7 个子命令 `secrets-scan`：自研离线凭据扫描（21 条高精度规则
#:                + 按字符集分档的熵闸 + 仓库自有注解），不依赖 gitleaks 二进制。
#:   1.1.0        新增第 8 个子命令 `facts`（机器事实采集/判定），`_facts` 包映射；
#:                `measure` 支持**无仓模式** —— 换机后只装包、未 clone 仓也能采集本机
#:                盘位/运行时/工具链，仓与远端两段显式标注「未采集 ≠ 0」。
#:                同批把 `verify_facts` 的判据加载改为「包内优先、仓内兜底」，
#:                修掉装包后 `parents[2]/tools/...` 恒 ENV ERROR 的仓耦合。
__version__ = "1.1.1"
