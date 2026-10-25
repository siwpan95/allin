"""repocheck 冒烟测试（离线、纯逻辑，使用 tempfile 造数据）。

不依赖 GUI、不依赖真实仓库。直接运行即可：
    python test_scanner.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Windows 控制台编码修复：测试输出含 ✅/✓ 等符号，GBK 代码页无法编码
import sys
if sys.stdout and getattr(sys.stdout, "encoding", "").lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


from scanner import check_project, discover_projects, dump_profile


def _build_fake_tree(base: Path) -> None:
    """在 base 下构造用于测试的假目录结构：

    repo_a/   一个“不合格”的 Python 项目：有 .py 但缺 .git / README / 测试 / 依赖 / LICENSE
              main.py 里 import 了一个明显不存在的模块（触发 import 断裂风险）
    repo_b/   一个“健康”项目：含 .git / README / tests / pyproject.toml / LICENSE
    notes/    普通文件夹（仅一个 txt），不应被识别为项目
    """
    # --- repo_a：问题项目 ---
    repo_a = base / "repo_a"
    repo_a.mkdir()
    (repo_a / "main.py").write_text(
        "import os\nimport numpy\nimport totally_missing_module_xyz\n", encoding="utf-8"
    )
    # 故意不创建 .git / README / tests / 依赖 / LICENSE

    # --- repo_b：健康项目 ---
    repo_b = base / "repo_b"
    repo_b.mkdir()
    (repo_b / ".git").mkdir()
    (repo_b / "README.md").write_text("# repo_b\n", encoding="utf-8")
    (repo_b / "pyproject.toml").write_text("[project]\nname='b'\n", encoding="utf-8")
    (repo_b / "LICENSE").write_text("MIT\n", encoding="utf-8")
    tests = repo_b / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo_b / "app.py").write_text("import os\n", encoding="utf-8")

    # --- repo_c：旧路径残留 + 内联引擎缺 patch ---
    repo_c = base / "repo_c"
    repo_c.mkdir()
    (repo_c / "README.md").write_text("# repo_c\n", encoding="utf-8")
    (repo_c / "tests").mkdir()
    (repo_c / "tests" / "test_x.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo_c / "requirements.txt").write_text("", encoding="utf-8")
    (repo_c / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (repo_c / ".git").mkdir()
    (repo_c / "start.bat").write_text('cd /d "D:\\allin\\tools\\x"\n', encoding="utf-8")
    (repo_c / "alloy").mkdir()
    (repo_c / "alloy" / "core.py").write_text("import os\n", encoding="utf-8")

    # --- notes：非项目 ---
    notes = base / "notes"
    notes.mkdir()
    (notes / "todo.txt").write_text("买牛奶\n", encoding="utf-8")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="repocheck_test_"))
    try:
        _build_fake_tree(tmp)

        # 1) 发现项目
        projects = discover_projects(str(tmp))
        print(f"[discover] 发现项目：{projects}")
        assert len(projects) == 3, f"应发现 3 个项目，实际 {len(projects)}"
        names = {os.path.basename(p) for p in projects}
        assert {"repo_a", "repo_b", "repo_c"} == names, f"项目名不符：{names}"

        # 2) 检查问题项目 repo_a
        repo_a_path = str(tmp / "repo_a")
        ra = check_project(repo_a_path)
        print(f"[check] {ra['name']} 问题：{ra['issues']}")
        need = {
            "无版本控制（缺 .git）",
            "无 README",
            "无测试",
            "无依赖声明",
            "无 LICENSE",
        }
        missing = need - set(ra["issues"])
        assert not missing, f"repo_a 漏报问题：{missing}"
        # import 断裂风险应出现，并包含我们故意写的模块
        broken = [s for s in ra["issues"] if s.startswith("疑似 import 断裂风险")]
        assert broken, "应检测到 import 断裂风险"
        assert "totally_missing_module_xyz" in broken[0], f"import 风险未包含目标模块：{broken}"

        # 3) 检查健康项目 repo_b（应无明显问题）
        rb = check_project(str(tmp / "repo_b"))
        print(f"[check] {rb['name']} 问题：{rb['issues']}")
        assert rb["issues"] == [], f"repo_b 应为健康项目，却有问题：{rb['issues']}"

        # 4) 指标合理性
        assert ra["metrics"]["py_files"] >= 1
        assert rb["metrics"]["has_git"] is True

        # 5) 纪律规则：旧路径残留 + 内联引擎缺 patch
        rc = check_project(str(tmp / "repo_c"))
        print(f"[check] {rc['name']} 问题：{rc['issues']}")
        stale = [s for s in rc["issues"] if s.startswith("旧仓库路径残留")]
        assert stale and "start.bat" in stale[0], f"应检出旧路径残留：{rc['issues']}"
        patch = [s for s in rc["issues"] if s.startswith("内联引擎副本缺")]
        assert patch, f"应检出内联引擎缺 patch：{rc['issues']}"

        # 6) 装配自省：8 条规则清单
        profile = dump_profile()
        assert profile["tool"] == "repocheck"
        assert len(profile["rules"]) == 8, f"应有 8 条规则，实际 {len(profile['rules'])}"
        assert any("旧仓库路径残留" in r["label"] for r in profile["rules"])
        print(f"[profile] 规则数：{len(profile['rules'])}")

        print("\n✅ 全部冒烟测试通过。")
    finally:
        # 清理临时目录
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
