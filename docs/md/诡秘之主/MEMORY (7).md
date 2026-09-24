# 项目记忆 — 诡秘之主序列途径模拟系统

## 项目路径
`D:\allin\project_root`

## 技术栈
- Python 3.14，零外部依赖
- 架构：数据驱动 + 类继承双模式

## 核心模块
| 文件 | 职责 |
|------|------|
| pathways_data.py | 22条途径完整数据 |
| pathway_groups.py | 途径组/互换/旧日体系 |
| sequences.py | 序列基类+数据驱动Sequence |
| ascension.py | 晋升/仪式/途径切换/性别转换 |
| anchor.py | 人性锚定系统 |
| pollution.py | 污染/疯狂/失控 |
| uniqueness.py | 唯一性+序列1特性 |
| role_playing.py | 扮演循环模拟 |
| main.py | 多模式演示入口 |

## 运行
```bash
cd D:/allin/project_root
python main.py [world|basic|multi|switch|full|gender|all]
```

## 设计原则
- 中文命名、中文注释
- keep it simple，快速出活
- 数据驱动，避免为220+序列写220+个类
- 向后兼容：原有 Thief/Fraudster 仍然可用
