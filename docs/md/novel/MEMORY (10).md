# D:\allin\novel — 项目速查

## 项目定位
中文随机句子生成器（语文教学工具），从POS词库挑选词语、按句型模板组装句子，支持语法树可视化和拼音显示。

## 数据层
- **POS词库**：`resources/pos_json/*.json`（13个文件：12词性+补语，6,473条）
- **POS Excel**：`resources/pos_excel/*.xlsx`（Excel编辑入口）
- **词典源**：`XDHYCD7th.txt`（现代汉语词典第7版，6.3万词条）

## 应用层
- `main.py` — POS版Builder，18种句型模板，拼音/详情/查词功能
- UI 1200×800，Checkbutton切换拼音显示

## 工具层（tools/，5个脚本）
| 脚本 | 功能 | 用法 |
|------|------|------|
| `rebuild_pos_banks.py` | 词典→POS全覆盖重建 | 直接运行 |
| `expand_from_dict_v2.py` | 增量扩充POS词库 | `--dry-run`预览；`--pos 名词`指定 |
| `add_pinyin_def_v2.py` | 补充拼音释义 | `--dry-run`预览；`--pos 补语`指定 |
| `excel_to_json.py` | POS Excel↔JSON | `--reverse`反向同步 |
| `expand_ai.py` | DeepSeek API扩充 | 需API额 |

## 关键设计决策
- 词库按**词性**（名词/动词/形容词……）组织，而非语法角色（主语/谓语……）
- Builder的 `_apply_affix()` 按来源词性智能加词缀（定语加"的"、状语条件加"地"）
- 补语词库手工维护，拼音释义从POS词典自动查找
- 不需要错题集功能（生成内容本身就是练习材料）
