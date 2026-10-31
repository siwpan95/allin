"""allin-governance —— 工作区治理中枢的可安装出口。

**这个包是什么**：把 `allin` 治理仓里那些**本来就通用**的部分装成一个可安装件，
让「外部的人」能直接消费，而不是读 86 份文档。

它当前提供：

* `repocheck` —— 离线仓库体检，30 条规则，零第三方依赖。
  真身在仓内 `tools/repocheck/`，本包打包时映射进来（**源码只有一份**）。

设计取向（与 REC-AU-21 的方向一致）：
* 治理工具必须**能在什么都没装的机器上跑** —— 所以运行时零第三方依赖；
* 判据必须**可复跑** —— 所以它是离线只读、不联网、不执行被测代码；
* 一个发布面，多个子命令 —— 所以 `repocheck` 是子命令而不是独立包。

    $ allin-governance --version
    $ allin-governance repocheck <目录>
"""

from __future__ import annotations

__all__ = ["__version__"]

#: 与 pyproject 的 project.version 保持一致。
#: 0.0.0a0 是**占位版本**（REC-AU-21 D1.3）：先占住 `allin-governance` 这个名字，
#: 再按实际形态发正式版。PyPI 新建项目有配额（20 次/小时），占名要一次成功。
__version__ = "0.0.0a0"
