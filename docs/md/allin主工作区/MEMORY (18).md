# 项目长期记忆

## tools/dictionary（D:/allin/tools/dictionary）数据特性
- `chinese-xinhua/data/ci.json`：**文学词典**，26 万词语，但**无词性标签**（仅 {ci, explanation}），生僻复合词极多，不适合直接当常用词库。
- `chinese-xinhua/data/word.json`：16142 汉字，仅 **1665** 个带〈POS〉标记 → 副词基本无法靠首字分类。
- `chinese-dictionary/chinese-dictionary-main/character/common/char_common.json`：**3500 常用字频率表**（{index, char, frequency}，frequency 0=最常用层）→ 用作过滤 ci.json 的「常用性」闸门。
- `chinese-dictionary/chinese-dictionary-main/word/word.json`：**32 万现代词典但也是文学大词典**，99.9% 含 ci.json 全部词 → 不能当常用词闸门。
- 沙箱无外网（WebSearch fetch failed）→ 取不到外部词级频率表，本地只有单字频率表（char_common）。
- `chinese-xinhua/data/idiom.json`：30895 成语（含拼音/释义/出处/例句），`xiehouyu.json`：14032 歇后语（谜面/谜底）——结构化好，适合直接接入中文生成类项目。
- CC-CEDICT 释义是英文，不适合中文教学词库。
- MakeMeAHanzi 用特殊字形编码（非标准 CJK 码位），按标准汉字取「结构」很绕，跳过。

## novel 项目（D:/allin/right/novel）增强约定
- 用 `tools/enhance_from_xinhua.py` 把 tools/dictionary 转成本项目词库（resources/pos_json/）。
- 名词池从 ci.json 安全扩充；动词/形容词靠 word.json 首字〈POS〉尽力补；副词保持原样。
- 生成器 `_pick_from` 对词库前段（精选词）70% 加权，扩充词只作多样性点缀。
- **频率闸门 `FREQ_MAX`**（enrich_from_xinhua.py 顶部常量）：0=最常用500字 / 1=2500常用字 / 2=3397常用+次常用。统一作用于 ci.json 过滤、精选基线清洗(`_clean_base`)、生僻率指标。全哥定稿选 **2**（只剔真正生僻字，库容全保 4500/3500/2000，幂等）。
- **生僻率指标两种口径**：freq0(500字,过严,历史基线) 与 gate(freq≤FREQ_MAX)。验证文章相对 gate=0.0%；相对 freq0≈24.7%（多为常用字里的 500~2500 位，仍属教学范围）。想连 freq0 也归零改 FREQ_MAX=1 即可（库容仍全保，只是多换精选词为 ci.json 词）。
- 验证脚本 `tools/validate_articles.py`：无头导入 main.Builder/Composer，生成 N 篇×M 句写 output/验证_增强后_文章{1..N}.txt 并量化生僻率（需系统 Python，因其带 tkinter）。
