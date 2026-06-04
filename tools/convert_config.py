# -*- coding: utf-8 -*-
"""
配置转换工具：JSON ↔ Excel 双向转换
用法:
    # 从 JSON 生成 Excel（策划入口）
    python tools/convert_config.py export

    # 从 Excel 同步回 JSON
    python tools/convert_config.py import

    # 直接运行可交互式选择
    python tools/convert_config.py
"""
import sys
import os

# 确保项目路径在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import openpyxl
except ImportError:
    print("错误: openpyxl 未安装，请先运行: pip install openpyxl")
    sys.exit(1)

from src.app.services.excel_service import ExcelService


def get_paths():
    """获取 JSON 和 Excel 的路径"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_dir = os.path.join(base_dir, "src", "resources", "data")
    excel_dir = os.path.join(base_dir, "src", "resources", "config")
    excel_path = os.path.join(excel_dir, "game_config.xlsx")
    return json_dir, excel_path


def export_to_excel():
    """从 JSON 导出到 Excel"""
    json_dir, excel_path = get_paths()
    print(f"JSON 数据目录: {json_dir}")
    print(f"Excel 输出路径: {excel_path}")
    print("-" * 50)
    ExcelService.export_from_json(json_dir, excel_path)
    print("-" * 50)
    print("导出完成！现在可以通过修改 game_config.xlsx 来更新游戏数据。")


def import_from_excel():
    """从 Excel 导入到 JSON"""
    json_dir, excel_path = get_paths()
    import json

    if not os.path.isfile(excel_path):
        print(f"错误: Excel 文件不存在: {excel_path}")
        print("请先运行: python tools/convert_config.py export")
        return

    es = ExcelService(excel_path)
    print(f"Excel 文件: {excel_path}")
    print(f"JSON 输出目录: {json_dir}")
    print("-" * 50)

    # 读取敌人模板
    enemies = es.get_enemy_templates()
    enemy_path = os.path.join(json_dir, "enemy_templates.json")
    with open(enemy_path, "w", encoding="utf-8") as f:
        json.dump({"enemy_templates": enemies}, f, ensure_ascii=False, indent=2)
    print(f"[OK] 敌人模板: {len(enemies)} 条 -> {enemy_path}")

    # 读取任务模板
    quests = es.get_quest_templates()
    quest_path = os.path.join(json_dir, "quest_templates.json")
    with open(quest_path, "w", encoding="utf-8") as f:
        json.dump({"quest_templates": quests}, f, ensure_ascii=False, indent=2)
    print(f"[OK] 任务模板: {len(quests)} 条 -> {quest_path}")

    # 读取物品模板
    items = es.get_item_templates()
    item_path = os.path.join(json_dir, "item_templates.json")
    with open(item_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"[OK] 物品模板 -> {item_path}")

    print("-" * 50)
    print("导入完成！JSON 文件已从 Excel 同步更新。")


def validate_excel():
    """验证 Excel 文件内容"""
    json_dir, excel_path = get_paths()

    if not os.path.isfile(excel_path):
        print(f"错误: Excel 文件不存在: {excel_path}")
        return

    es = ExcelService(excel_path)
    print("=" * 50)
    print("Excel 配置文件验证")
    print("=" * 50)

    enemies = es.get_enemy_templates()
    print(f"\n[敌人模板] ({len(enemies)} 条):")
    for e in enemies:
        print(f"  [{e['level']}级] {e['name']} | HP:{e['hp']} 伤害:{e['damage']} 经验:{e['exp']}")

    quests = es.get_quest_templates()
    print(f"\n[任务模板] ({len(quests)} 条):")
    for q in quests:
        print(f"  [{q['quest_id']}] {q['name']} ({q.get('type','?')}) Lv.{q['level_req']}")

    items = es.get_item_templates()
    weapons = items.get("weapon_templates", {})
    armors = items.get("armor_templates", {})
    print(f"\n[武器类型]: {list(weapons.keys())}")
    print(f"[护甲类型]: {list(armors.keys())}")
    quality = items.get("quality_settings", {})
    print(f"[品质倍率]: 伤害={len(quality.get('QUALITY_DAMAGE_MULT',{}))}级 防御={len(quality.get('QUALITY_DEFENSE_MULT',{}))}级")
    print(f"[特效池]: {items.get('effect_pool', [])}")


def print_usage():
    """打印使用说明"""
    print("=" * 50)
    print("蜂蜜挂机 RPG - 配置转换工具")
    print("=" * 50)
    print("\n用法:")
    print("  python tools/convert_config.py export    从JSON生成Excel(首次使用)")
    print("  python tools/convert_config.py import    从Excel同步回JSON")
    print("  python tools/convert_config.py validate  验证Excel数据")
    print("")
    print("工作流程:")
    print("  1. export  → 生成 game_config.xlsx")
    print("  2. 用 Excel 编辑 game_config.xlsx")
    print("  3. import  → 将 Excel 数据同步到 JSON")
    print("  (或直接使用 Excel，游戏会自动优先读取 Excel)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
    else:
        print_usage()
        cmd = input("\n请选择操作 [export/import/validate]: ").strip().lower()

    if cmd == "export":
        export_to_excel()
    elif cmd == "import":
        import_from_excel()
    elif cmd == "validate":
        validate_excel()
    else:
        print(f"未知操作: {cmd}")
        print_usage()
