# Blur 项目 — 长期记忆

## 架构原则
- ECS架构：py负责逻辑 + JSON负责内容，完全解耦
- 零硬编码注册表：`_CLASS_MAP` 由 `__subclasses__()` 自动构建，`@register_effect` 装饰器收集元数据
- 添加新效果流程：定义 `@register_effect(id, name, category, background)` 类 → 运行 `python effects/generate.py` → 无需修改注册表
- 参数化变体：在 effects/ 创建JSON，`class` 指向已有类名即可
- 配置加载链：Excel → JSON兜底 → 硬编码默认值

## 工具链
- `tools/auto_registry.py`: JSON ↔ Python类对齐验证
- `effects/generate.py`: 从 @register_effect 元数据自动生成JSON
- Python venv: `C:/Users/13122/.workbuddy/binaries/python/envs/default/`

## 文件约定
- 效果类定义: `systems/render_system.py`
- 效果JSON: `effects/XX_effect_id.json`
- 背景主题JSON: `effects/themes.json`
- 全局配置: `data/config.json`
- 备份: `D:\allin\AA\blur_YYYYMMDD_HHMMSS\`
