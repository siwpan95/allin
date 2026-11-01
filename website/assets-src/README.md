# 配图源文件（assets-src/）

> 这里的文件**不是**网站的公开资源：`npm run seed` 会把它们加密写进数据库，
> 页面只能经 `/media/<asset_key>` 拿到字节。本目录的作用只是**可复现的种子源**，
> 部署到线上时可以删掉本目录（数据已经在库里了）。

## 一、命名规范

```
site_<page>_<slot>_<nn>.<ext>
└┬─┘ └──┬──┘ └─┬──┘ └┬┘ └──┘
  │      │      │     │     └─ 扩展名：.jpg（AI 生成的照片类）/.png（需透明或图形类）/.svg（矢量）
  │      │      │     └─────── 两位序号 01–99（同一槽位多张备选）
  │      │      └───────────── 语义槽位：hero / dev / ops / gov / team / grid / banner …
  │      └──────────────────── 页面：home / services / about / contact / share（跨页复用）
  └─────────────────────────── 项目前缀，固定 site
```

规则：

1. **全部小写 ASCII**，只允许 `[a-z0-9_.]`，禁止中文、空格与大写（避免跨平台大小写与编码问题）
2. **文件名即资产标识**：入库后的 `asset_key` = 文件名去掉扩展名，例如 `site_home_hero_01.jpg` → `site_home_hero_01`
3. **一个槽位一张主图**，备选用序号递增，页面只引用主图（`_01`）
4. **体积**：单文件 < 1 MiB（仓库提交钩子对单文件的硬上限），当前清单均为 JPEG q82、长边 ≤ 1440
5. **描述信息不外露**：标题 / alt / 作用域属于元数据，写入时同样加密（见 `meta_cipher` 列）

## 二、当前清单

| 文件名 | asset_key | 尺寸 | 体积 | 用途 | 生成说明 |
|---|---|---|---|---|---|
| `site_home_hero_01.jpg` | `site_home_hero_01` | 1440×960 | 269 KB | 首页主视觉 | AI 生成：霓虹数据城夜景，青/品红光带 |
| `site_services_dev_01.jpg` | `site_services_dev_01` | 1024×1024 | 95 KB | 服务 DEV 配图 | AI 生成：全息代码编辑界面 |
| `site_services_ops_01.jpg` | `site_services_ops_01` | 1024×1024 | 208 KB | 服务 OPS 配图 | AI 生成：霓虹机房与巡检机械臂 |
| `site_services_gov_01.jpg` | `site_services_gov_01` | 1024×1024 | 266 KB | 服务 GOV 配图 | AI 生成：治理门禁流水线与发光盾牌 |
| `site_about_team_01.jpg` | `site_about_team_01` | 1024×1024 | 189 KB | 关于我们配图 | AI 生成：赛博风格工作室 |
| `site_contact_grid_01.jpg` | `site_contact_grid_01` | 1024×1024 | 187 KB | 联系我们配图 | AI 生成：霓虹通讯枢纽与地球网格 |
| `site_share_banner_01.jpg` | `site_share_banner_01` | 1440×960 | 206 KB | 通用横幅（跨页复用） | AI 生成：霓虹电路横幅 |

新增配图时：按规范命名 → 放进本目录 → `npm run seed`（幂等，只新增/覆盖同名 key）。

## 三、来源与许可

- 全部由 AI 生成（工具：ImageGen，日期：2026-11-01），提示词要求"无文字、无水印"，不引入第三方版权素材
- 生成后统一处理：转 JPEG、quality 82、渐进式、长边缩放至 ≤1440，以满足仓库单文件体积约束
- 若替换为品牌素材或第三方图，请在此表补记**来源与许可**，并同步更新 `scripts/seed.js` 的 `IMAGE_META`
