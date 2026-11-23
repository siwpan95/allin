"""
测试探针系统 — 通过插入轻量级探针进行冒烟测试。

概念：
    测试探针（Probe）是在关键路径上插入的轻量检测点。
    不改变被测代码逻辑，仅在关键节点做快速验证。
    适合 CI/CD 冒烟测试、部署后健康检查、快速回归验证。

设计原则：
    - 探针是无副作用的只读检查
    - 批量触发，快速扫过所有探针点
    - 失败探针记录详细上下文
"""

import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

from .error_types import ErrorCode, TestError, ErrorCategory
from .log_manager import LogManager


@dataclass
class Probe:
    """单个测试探针

    Args:
        name: 探针名称（唯一标识）
        check: 检查函数，返回 (passed: bool, detail: str)
        category: 探针分类（如 "启动", "数据库", "API", "UI"）
        priority: 优先级 1-5，1 最高（数字越小越优先扫描）
        tags: 标签集合，用于按标签筛选探针
        timeout: 超时秒数
    """
    name: str
    check: Callable[[], tuple[bool, str]]
    category: str = "通用"
    priority: int = 3
    tags: Set[str] = field(default_factory=set)
    timeout: float = 3.0

    def run(self) -> TestError:
        """执行探针检测，返回 TestError"""
        start = time.perf_counter()
        try:
            passed, detail = self.check()
        except Exception as e:
            duration = time.perf_counter() - start
            return TestError(
                error_code=ErrorCode.PROBE_FAIL,
                message=f"{type(e).__name__}: {e}",
                test_name=f"[探针] {self.name}",
                traceback=traceback.format_exc(),
            )

        duration = time.perf_counter() - start
        if passed:
            return TestError(
                error_code=ErrorCode.PROBE_PASS,
                message=f"✅ {detail} ({duration:.3f}s)",
                test_name=f"[探针] {self.name}",
            )
        else:
            return TestError(
                error_code=ErrorCode.PROBE_FAIL,
                message=f"❌ {detail} ({duration:.3f}s)",
                test_name=f"[探针] {self.name}",
            )


class ProbeManager:
    """探针管理器 — 注册、筛选、批量执行"""

    def __init__(self, log_manager: LogManager):
        self.log = log_manager
        self._probes: List[Probe] = []

    # ── 注册 ──
    def register(self, probe: Probe):
        """注册一个探针"""
        self._probes.append(probe)

    def register_batch(self, probes: List[Probe]):
        """批量注册探针"""
        self._probes.extend(probes)

    @property
    def count(self) -> int:
        return len(self._probes)

    # ── 筛选 ──
    def filter(self, *, category: str = None, tags: Set[str] = None,
               max_priority: int = None) -> List[Probe]:
        """按条件筛选探针

        Args:
            category: 按分类筛选
            tags: 按标签筛选（包含任一标签即匹配）
            max_priority: 最大优先级（数字），只返回优先级 <= 此值的探针
        """
        result = self._probes
        if category:
            result = [p for p in result if p.category == category]
        if tags:
            result = [p for p in result if p.tags & tags]
        if max_priority is not None:
            result = [p for p in result if p.priority <= max_priority]
        return result

    def smoke_probes(self) -> List[Probe]:
        """获取冒烟探针：仅 priority=1 的关键路径探针"""
        return self.filter(max_priority=1)

    def quick_probes(self) -> List[Probe]:
        """获取快速探针：priority <= 2"""
        return self.filter(max_priority=2)

    # ── 执行 ──
    def run(self, probes: List[Probe] = None) -> List[TestError]:
        """批量执行探针

        Args:
            probes: 要执行的探针列表。None 表示全部。

        Ctrl+C 处理：
            中断后保留已完成的结果，打印部分汇总后退出。
        """
        targets = probes if probes is not None else self._probes
        results = []
        total = len(targets)
        interrupted = False

        self.log.section(f"📍 探针扫描 — {total} 个检测点")

        try:
            for i, probe in enumerate(targets, 1):
                tag_str = f"[{probe.category}]" if probe.category else ""
                self.log.info(f"[{i}/{total}] {tag_str} 探针: {probe.name}")

                try:
                    result = probe.run()
                except KeyboardInterrupt:
                    raise  # 重新抛出给外层 catch
                self.log.print_result(result.error_code, result.test_name)
                self.log.error(result)
                results.append(result)

        except KeyboardInterrupt:
            interrupted = True
            remaining = total - len(results)
            self.log.section("⚠️  用户中断 (Ctrl+C)")
            self.log.warning(f"已执行 {len(results)}/{total} 个探针，剩余 {remaining} 个未执行")
            self.log.print_colored(f"\n⚠️  用户中断 — 已扫描 {len(results)}/{total} 个探针", bold=True)

        passed = sum(1 for r in results if r.error_code.category == ErrorCategory.PASS)
        failed = len(results) - passed

        if interrupted:
            self.log.info(f"中断前结果: {passed}/{len(results)} 通过, {failed} 失败")
        else:
            self.log.info(f"探针扫描完成: {passed}/{total} 通过, {failed} 失败")

        return results

    def run_smoke(self) -> List[TestError]:
        """执行冒烟测试（仅 priority=1 的关键探针）"""
        probes = self.smoke_probes()
        self.log.section("🔥 冒烟测试 — 关键路径检测")
        return self.run(probes)

    def run_category(self, category: str) -> List[TestError]:
        """按分类执行探针"""
        probes = self.filter(category=category)
        self.log.section(f"📍 分类扫描: {category}")
        return self.run(probes)

    # ── 快捷探针工厂 ──
    @staticmethod
    def simple(name: str, condition: bool, detail: str = "",
               category: str = "通用", priority: int = 3,
               tags: Set[str] = None) -> Probe:
        """快速创建条件探针

        Args:
            name: 探针名称
            condition: 检查条件（True = 通过）
            detail: 详情描述
            category: 分类
            priority: 优先级
            tags: 标签
        """
        return Probe(
            name=name,
            check=lambda c=condition, d=detail: (c, d if d else f"条件{'满足' if c else '不满足'}"),
            category=category,
            priority=priority,
            tags=tags or set(),
        )
