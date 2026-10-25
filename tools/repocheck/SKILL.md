---
name: repocheck
description: Maintain the repocheck repo health tool (G:/tools/dev/repocheck). Self-contained scanner with 8 health checks including discipline rules.
agent_created: true
---

# repocheck 仓库体检工具维护

## 概述
自包含桌面小工具：识别根目录下项目并做 8 项体检（版本控制/README/测试/依赖/LICENSE/import 断裂启发式/旧仓库路径残留/内联引擎缺 patch），支持 CSV/HTML 报告。复制优于共享：不 import 其他工具。

## 结构
- scanner.py：纯逻辑（discover_projects / check_project + 8 规则）
- main.py：Tk GUI + 命令行模式（main.py <root>）
- test_scanner.py：冒烟测试（tempfile 造数据）

## 常用命令
- 冒烟：python test_scanner.py（✅ 全过）
- 命令行扫描：python main.py G:\crawlers

## 关键约定
- 规则即数据：新规则 = check_project 加检查 + helper + README 表 + 冒烟测试四处同步
- 纪律规则（2026-08-23 新增）：旧仓库路径残留(D:/allin)、内联引擎副本缺 engine.patch.yaml
- import 断裂是启发式（COMMON_THIRD_PARTY 手写清单），误报允许、标签带"疑似"前缀

## 已知陷阱
- 排除目录在 DEFAULT_EXCLUDE，新增大目录记得加（否则扫描慢）
- GBK 控制台：test_scanner 已 reconfigure utf-8
- 项目识别限于一级子目录（对单项目目录扫描时会把 tests/ 等子目录当"项目"——预期行为）
