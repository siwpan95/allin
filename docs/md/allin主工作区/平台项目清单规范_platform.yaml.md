# platform.yaml 项目清单规范 v1（草案 · 平台立项 P0 交付）

> 2026-08-25。定位：crawler-plugin 规范（crawl_hub/PLUGIN_SPEC.md）的**全项目泛化**——
> 每个接入平台的项目 = 一个清单文件，平台只登记/启停/审计，绝不 import 项目代码（子进程隔离）。

## 清单形态

一个接入项目 = 一个 `platform.yaml`，放在项目根目录（或平台 registry/ 集中登记，二选一由拍板决定）：

```yaml
id: radio                    # 唯一 id（小写+连字符）
name: 电台                     # 显示名
category: media              # 分类：media / tool / game / engine / ai / crawler / music
version: 1.0.0               # 独立更新标识
port: 8000                   # 若提供服务：必须与 ports.yaml 登记一致（查表纪律）
launch:                      # 启动（子进程，cwd=项目目录）
  command: npm run radio
stop:                        # 停止（可选；缺省 = 结束子进程树）
  command: npm run stop-radio
health:                      # 健康检查（可选；缺省 = 端口探活）
  url: http://localhost:8000/api/status
publish:                     # 发布面（gitee，开源优先）
  repo: siwpan/private-radio-stations
  branch: 3.0
manual: false                # true = 只登记不自动启动（GUI 类项目）
```

## 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| id | ✅ | 唯一 id |
| name | ✅ | 显示名 |
| category | ✅ | 分类（库页分组） |
| version | ✅ | 语义化版本（独立更新标识） |
| port | 可选 | **有服务必填**：值必须先在 ports.yaml/端口分配表登记（register 校验 fail-loud） |
| launch | ✅ | 启动命令（子进程隔离，绝对路径纪律同 crawl_hub） |
| stop | 可选 | 停止命令。**dispose 纪律（2026-08-27）**：launch 必须可逆——非 manual 服务型条目有优雅停止脚本必须声明（如 radio/video 已声明 stop-radio.bat/stop-video.bat）；缺省 = 平台按 PID 树杀（taskkill /T /F），任务日志记录 stop-graceful / stop-force / stop 三类动作。`check.mjs` 对未声明 stop 的非 manual 条目给出非阻塞提示 |
| health | 可选 | 健康检查 url；缺省=port 探活 |
| publish | 可选 | gitee 发布面（工坊订阅来源） |
| manual | 可选 | 手动启动型（GUI），默认 false |
| config | 可选 | 配置 schema 提示（键值说明，配置即数据） |

## 纪律（继承 crawl_hub + 三件事）

1. **独立更新**：每个项目独立版本、独立目录、独立发布；平台更新一个不动其他（合流定理）。
2. **子进程隔离**：launch = subprocess；崩一个不影响平台与其他项目（helminth 教训）。
3. **统一端口**：port 必查 ports.yaml；平台 register 时校验，未登记拒绝登记（fail-loud）。
4. **日志即事实源**：启停/退出/退出码/时长全部写 JSONL（与 WorldLog/tasks.log 同构），可审计。
5. **开源优先**：publish.repo 必须公开 + MIT（铁律 0）。

## 与 crawler-plugin 规范的关系

- crawler-plugin（crawl_hub 域）= 本规范的爬虫子集（interface: discover/download 等能力接口字段仅爬虫域需要）；
- 平台库页可把 crawl_hub 的插件目录一并聚合（crawl_hub 自身作为一个 platform.yaml 项目 + 其 plugins/ 按 manifest 显示）；
- 两套规范同源：manifest/清单 = 声明，宿主 = 装配，端口 = 查表，日志 = JSONL。

## 首批接入清单（待拍板；草案）

| id | port | launch |
|---|---|---|
| radio | 8000 | npm run radio |
| video | 8100 | npm run video |
| portal | 9000 | npm run portal（平台自身，自举） |
| crawl-hub | — | python launcher.py（GUI 型：manual=true） |
| audio-pipeline | — | python pipeline.py（按实际入口） |
| audio-separator | 8080 | python web_server.py（按实际入口） |
| mixer | 8010 | python mixer_stream.py（按实际入口） |
| alloy | — | python -m alloy dump-profile（只读视图，非进程） |
