# allin-platform —— Steam 式全项目集成平台

> 立项：G:\docs\md\allin主工作区\平台立项报告_Steam式集成_2026-08-25.md（2026-08-25 用户拍板：Node+Cordis 栈 / 新建本仓 / 单机工坊+静态目录 / 首批 8 项目）。

## 定位

**聚合不融合**：把 G:\ 全部活跃项目集成到一个平台（类似 Steam 的库 + 创意工坊），但平台零业务代码——项目仍是独立进程、独立目录、独立更新；平台只做 **登记 / 启停 / 装配 / 审计**。

- 理论支持：三条整合纪律（每个插件独立更新 / 不盲目整合 / 统一端口）+ 三件事（注册即回滚 / 补丁即差异 / 日志即事实源）；
- 教训约束：helminth/media_engine 失败 = 代码级融合 → 本平台**绝不 import 项目代码**（子进程隔离，crawl_hub 模式）；
- 端口纪律：任何新服务端口先查 `G:\docs\md\allin主工作区\ports.yaml`（与端口分配表.md 同步的唯一事实源）。

## 结构

```
apps/portal/         平台前台 :9000（零依赖纯 Node http）：
                     库 Library（项目卡片/启停/状态） · 工坊 Workshop（订阅/取消） · 引擎 Engine（alloy 装配视图）
packages/core/       平台内核：registry（platform.yaml 加载+校验+端口查表）/ launch（子进程+JSONL 任务日志）/ workshop（订阅=clone 到 workshop-copies，更新=真实 git pull，回滚=checkout，退订=删除副本）/ gitee（发布面查询）/ probe
registry/projects/   首批 8 个项目的 platform.yaml（radio/video/portal/crawl_hub/audio_pipeline/audio_separator/mixer/alloy）
scripts/check.mjs    无 GUI 配置审计（exit 0=全通过，对齐 crawl_hub --check）
data/                运行时状态（tasks.log JSONL + workshop.json，gitignored）
```

## 快速开始

```bash
cd G:\platform
npm install --registry=https://registry.npmmirror.com
npm run check      # 注册表审计（端口查表 + 必填字段 fail-loud）
npm test           # 内核 + 前台测试
npm run portal     # http://localhost:9000（库/工坊/引擎三页签）
```

## 清单规范

每个接入项目一个 `platform.yaml`（字段：id/name/category/version/path/port/launch/stop/health/publish/manual），详见《平台项目清单规范_platform.yaml.md》。port 必查 ports.yaml，未登记拒绝登记。

## 接入新项目

1. 在 `registry/projects/` 写一个 platform.yaml（先查 ports.yaml 再填 port）；
2. `npm run check` 通过；
3. 库页自动可见（子进程隔离启动）。

## 许可

MIT · Copyright (c) 2026 siwpan（铁律 0：开源优先，公开仓）。
