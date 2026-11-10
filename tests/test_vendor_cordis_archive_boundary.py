"""P2 / M-2 回归：vendored cordis 归档解压的 canonicalize-then-contain 边界。

审计证据：docs/记录/审计/深度审计报告_2026-11-10.md:329-335（Zip Slip / Tar Slip）。
原实现剥离归档第一层目录后直接拼 target / parts[1]，无 realpath 边界校验。
本测试用内存归档 + 假 urlopen（不联网、不需要 cordis 包依赖）验证：
  * 恶意成员名一律 ValueError，且不在目标目录外落盘；
  * 合法成员仍按原语义写入目标目录；
  * tar 的符号链接 / 硬链接 / 设备成员不物化到目标树。
"""
from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

CREATE_PY = (Path(__file__).resolve().parents[1]
             / "vendor" / "cordis" / "src" / "cordis" / "create.py")


def _load_create():
    """按文件路径加载，绕开 cordis/__init__.py 的 pyyaml/watchdog 硬依赖。"""
    spec = importlib.util.spec_from_file_location("allin_vendor_cordis_create", CREATE_PY)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _tar_payload(name: str, content: bytes = b"pwned") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:  # gov-python: allow (binary tar stream; encoding N/A)
        info = tarfile.TarInfo(name)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _zip_payload(name: str, content: bytes = b"pwned") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(name, content)
    return buf.getvalue()


def _drive_download(mod, monkeypatch, payload: bytes, filename: str, target: Path) -> None:
    monkeypatch.setattr(mod, "_file_candidates", lambda meta, version: [
        {"url": "https://example.invalid/" + filename, "packagetype": "sdist"}])
    monkeypatch.setattr(mod.urllib.request, "urlopen",
                        lambda url, timeout=None: _FakeResponse(payload))
    mod.download_template("https://example.invalid",
                          {"info": {"name": "pkg"}}, "1.0", target)


@pytest.fixture()
def create():
    return _load_create()


@pytest.mark.parametrize("bad_name", [
    "../../escaped.txt",
    "pkg/../../escaped.txt",
    "/etc/passwd",
    "//server/share/evil.txt",
    "C:/Windows/evil.txt",  # gov-python: allow (deliberate traversal payload)
    "..\\..\\escaped.txt",
    "\\\\server\\share\\evil.txt",
    "",
    "ok\x00evil.txt",
])
def test_safe_extract_path_rejects_traversal(create, tmp_path, bad_name):
    target = tmp_path / "extract"
    target.mkdir(parents=True)
    with pytest.raises(ValueError):
        create._safe_extract_path(target, bad_name)


def test_safe_extract_path_accepts_legitimate_nested_path(create, tmp_path):
    target = tmp_path / "extract"
    target.mkdir(parents=True)
    dest = create._safe_extract_path(target, "src/pkg/__init__.py")
    assert dest.is_relative_to(target.resolve())
    assert dest.name == "__init__.py"


def test_safe_extract_path_rejects_symlink_escape(create, tmp_path):
    target = tmp_path / "extract"
    target.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (target / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:  # Windows 无开发者模式
        pytest.skip(f"环境不支持创建符号链接：{exc}")
    with pytest.raises(ValueError):
        create._safe_extract_path(target, "link/evil.txt")


def test_tar_traversal_is_blocked_and_writes_nothing_outside(create, monkeypatch, tmp_path):
    target = tmp_path / "a" / "b" / "extract"
    payload = _tar_payload("pkg/../../escaped.txt")
    with pytest.raises(ValueError, match="unsafe tar member"):
        _drive_download(create, monkeypatch, payload, "pkg-1.0.tar.gz", target)
    assert not (tmp_path / "a" / "escaped.txt").exists()


def test_zip_traversal_is_blocked_and_writes_nothing_outside(create, monkeypatch, tmp_path):
    target = tmp_path / "a" / "b" / "extract"
    payload = _zip_payload("pkg/../../escaped.txt")
    with pytest.raises(ValueError, match="unsafe zip member"):
        _drive_download(create, monkeypatch, payload, "pkg-1.0.zip", target)
    assert not (tmp_path / "a" / "escaped.txt").exists()


def test_legitimate_tar_member_still_extracts(create, monkeypatch, tmp_path):
    target = tmp_path / "extract"
    payload = _tar_payload("pkg/src/__init__.py", b"VALUE = 1\n")
    _drive_download(create, monkeypatch, payload, "pkg-1.0.tar.gz", target)
    assert (target / "src" / "__init__.py").read_bytes() == b"VALUE = 1\n"


def test_legitimate_zip_member_still_extracts(create, monkeypatch, tmp_path):
    target = tmp_path / "extract"
    payload = _zip_payload("pkg/src/__init__.py", b"VALUE = 2\n")
    _drive_download(create, monkeypatch, payload, "pkg-1.0.zip", target)
    assert (target / "src" / "__init__.py").read_bytes() == b"VALUE = 2\n"


def test_tar_symlink_member_is_not_materialised(create, monkeypatch, tmp_path):
    target = tmp_path / "extract"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:  # gov-python: allow (binary tar stream; encoding N/A)
        link = tarfile.TarInfo("pkg/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        tar.addfile(link)
    _drive_download(create, monkeypatch, buf.getvalue(), "pkg-1.0.tar.gz", target)
    assert not (target / "link").exists()
