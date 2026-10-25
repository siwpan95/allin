"""项目上下文：单次目录索引 + 只读 git 封装 + 文本解码。

取代旧实现里 6 处各自 ``os.walk`` 的重复遍历；30 条规则共享同一份索引。
另外统一处理 Windows 下最容易踩的三件事：中文路径解码、GBK 文本回退、
以及 windowed exe 里 ``subprocess`` 弹黑窗。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import cached_property
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: windowed（console=False）exe 里调用 git 时不弹出控制台窗口。
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",   # 绝不等待凭据输入
    "GIT_OPTIONAL_LOCKS": "0",    # 只读调用不要抢索引锁
}

_GIT_TIMEOUT = 10

_GIT_BINARY: str | None = None
_GIT_PROBED = False


def git_binary() -> str | None:
    """返回 git 可执行文件路径；未安装则为 ``None``（模块级缓存）。"""
    global _GIT_BINARY, _GIT_PROBED
    if not _GIT_PROBED:
        _GIT_PROBED = True
        _GIT_BINARY = shutil.which("git")
    return _GIT_BINARY


def _run_git(args: list[str], cwd: Path) -> tuple[int, bytes]:
    """执行只读 git 命令，返回 ``(returncode, stdout)``。失败一律 ``(-1, b"")``。"""
    exe = git_binary()
    if exe is None:
        return -1, b""
    cmd = [exe, "-C", str(cwd), "-c", "core.quotepath=false", *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=_GIT_TIMEOUT,
            env=_GIT_ENV,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return -1, b""
    return proc.returncode, proc.stdout


def _decode(raw: bytes) -> str:
    """按 utf-8-sig → utf-8 → gbk 逐级回退解码文本。"""
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# git 只读封装
# ---------------------------------------------------------------------------

class Git:
    """针对单个项目目录的只读 git 视图（懒加载，不 spawn 直到被用到）。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._probed = False
        self._reason = ""
        self._nested: bool | None = None
        self._injected = False
        self._toplevel: str = ""

    # -- 探测 ---------------------------------------------------------------

    def _probe(self) -> None:
        """确认「有 .git + git 可用」，只做一次。

        这一步**不 spawn 任何子进程**（纯文件系统 + ``shutil.which``）：
        项目目录有 ``.git`` 时，``git -C <dir> ls-files`` 天然只返回该目录
        下已跟踪的文件，路径相对该目录 —— 实测已确认，因此不需要
        ``rev-parse --show-toplevel`` 来兜底父仓场景。
        """
        if self._probed:
            return
        self._probed = True

        if not (self.root / ".git").exists():
            self._reason = "no-dotgit"
            return
        if git_binary() is None:
            self._reason = "no-binary"

    def block_reason(self) -> str:
        """返回 ``""`` 表示 git 视图可用；非空为不可用原因。"""
        self._probe()
        return self._reason

    @property
    def ok(self) -> bool:
        """是否存在可用的 .git（能跑 ls-files）。"""
        return not self.block_reason()

    @property
    def nested(self) -> bool:
        """项目目录是否只是父仓的子目录（**会 spawn**，仅调试/诊断用）。"""
        if self._nested is not None:
            return self._nested
        self._nested = False
        if not self.ok:
            return False
        code, out = _run_git(["rev-parse", "--show-toplevel"], self.root)
        if code != 0:
            return False
        self._toplevel = os.fsdecode(out).strip()
        try:
            self._nested = Path(self._toplevel).resolve() != self.root.resolve()
        except OSError:
            self._nested = False
        return self._nested

    @property
    def repo_level_ok(self) -> bool:
        """是否能用 tag / commit 这类「仓级」信息。

        ``.git`` 存在即视为独立仓（submodule 与 worktree 的 ``.git`` 是文件，
        但它们的 tag 本来就属于自己那一层，用它是对的）。因此这里不做
        ``nested`` 探测 —— 那会为每个仓库白付一次子进程开销。
        """
        return self.ok and not self._injected

    # -- 数据 ---------------------------------------------------------------

    @cached_property
    def ls_files(self) -> tuple[str, ...]:
        """``git ls-files`` 的结果，项目内相对 POSIX 路径。"""
        if not self.ok:
            return ()
        code, out = _run_git(["ls-files", "-z", "--cached"], self.root)
        if code != 0:
            self._reason = "git-error"
            return ()
        return tuple(
            os.fsdecode(raw).replace("\\", "/")
            for raw in out.split(b"\x00")
            if raw
        )

    @cached_property
    def tags(self) -> tuple[str, ...]:
        """按版本号倒序的 tag 列表；仓级信息不可用时为空。"""
        if not self.repo_level_ok:
            return ()
        code, out = _run_git(["tag", "--sort=-v:refname"], self.root)
        if code != 0:
            return ()
        return tuple(t.strip() for t in os.fsdecode(out).splitlines() if t.strip())

    def latest_version_tag(self) -> str | None:
        """最新的语义化版本 tag（``v1.2.3`` 形式），没有则 ``None``。

        用途等同 ``git describe --tags --abbrev=0``，但复用 :attr:`tags` 的
        缓存，不再单独 spawn 一次 git。
        """
        import re

        pattern = re.compile(r"^v?\d+\.\d+\.\d+")
        for tag in self.tags:
            if pattern.match(tag):
                return tag
        return None

    @cached_property
    def commit_count(self) -> int:
        """HEAD 上的提交数；不可用时返回 0。"""
        if not self.repo_level_ok:
            return 0
        code, out = _run_git(["rev-list", "--count", "HEAD"], self.root)
        if code != 0:
            return 0
        try:
            return int(os.fsdecode(out).strip())
        except ValueError:
            return 0


# ---------------------------------------------------------------------------
# 项目上下文
# ---------------------------------------------------------------------------

class ProjectContext:
    """一个项目目录的只读视图，所有派生数据按需缓存。

    参数
    ----
    root: 项目目录。
    exclude: 需要跳过的目录名集合。
    git_files: 注入伪造的 ``git ls-files`` 结果（测试用，省掉 spawn git）。
    max_files: 索引文件数上限，超限即截断并置 ``truncated``。
    max_text_bytes: 单个文本文件读取上限。
    max_text_total: 整项目文本累计读取上限。这是**兜底**而非节流阀 ——
        设得太小会让靠后的规则集体读不到文件，所以给足余量（默认 64MB）。
    """

    def __init__(self, root: str | os.PathLike, exclude: set[str] | frozenset[str] = frozenset(),
                 *, git_files: tuple[str, ...] | None = None,
                 max_files: int = 20000,
                 max_text_bytes: int = 256 * 1024,
                 max_text_total: int = 64 * 1024 * 1024) -> None:
        self.root = Path(root)
        self.exclude = frozenset(exclude)
        self.truncated = False
        self._injected_git_files = git_files
        self._max_files = max_files
        self._max_text_bytes = max_text_bytes
        self._max_text_total = max_text_total
        self._text_cache: dict[str, str | None] = {}
        self._text_bytes = 0

    # -- 索引 ---------------------------------------------------------------

    @cached_property
    def _index(self) -> tuple[tuple[str, ...], dict[str, int], frozenset[str]]:
        """一次遍历产出 ``(文件列表, 文件大小表, 目录集合)``。"""
        files: list[str] = []
        sizes: dict[str, int] = {}
        dirs: set[str] = {""}
        # 显式栈而非 os.walk：能顺手拿到 entry.stat()（Windows 上无需额外 syscall）
        stack: list[tuple[str, Path]] = [("", self.root)]

        while stack:
            rel_dir, abs_dir = stack.pop()
            try:
                entries = list(os.scandir(abs_dir))
            except OSError:
                continue
            for entry in entries:
                name = entry.name
                rel = f"{rel_dir}/{name}" if rel_dir else name
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if name in self.exclude:
                            continue
                        dirs.add(rel)
                        if len(files) < self._max_files:
                            stack.append((rel, Path(entry.path)))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
                if len(files) >= self._max_files:
                    self.truncated = True
                    continue
                files.append(rel)
                sizes[rel] = size

        files.sort()
        return tuple(files), sizes, frozenset(dirs)

    @property
    def files(self) -> tuple[str, ...]:
        """项目内全部文件（相对 POSIX 路径，已排除 exclude 目录）。"""
        return self._index[0]

    @property
    def file_sizes(self) -> dict[str, int]:
        """文件相对路径 → 字节大小。"""
        return self._index[1]

    @property
    def dirs(self) -> frozenset[str]:
        """项目内全部目录（相对 POSIX 路径，含表示项目根的 ``""``）。"""
        return self._index[2]

    @cached_property
    def file_set(self) -> frozenset[str]:
        """文件路径集合，用于 O(1) 存在性判断。"""
        return frozenset(self.files)

    @cached_property
    def py_files(self) -> tuple[str, ...]:
        """全部 ``.py`` 文件。"""
        return tuple(f for f in self.files if f.endswith(".py"))

    @property
    def total_files(self) -> int:
        """文件总数。"""
        return len(self.files)

    # -- 目录/文件查询 ------------------------------------------------------

    def has(self, rel: str) -> bool:
        """路径（文件或目录）是否存在。"""
        return rel in self.file_set or rel in self.dirs

    def has_dir(self, rel: str) -> bool:
        """目录是否存在。"""
        return rel in self.dirs

    @cached_property
    def _children_index(self) -> dict[str, tuple[str, ...]]:
        """目录相对路径 → 其直接子条目名（文件与目录合并）。"""
        index: dict[str, list[str]] = {}
        for path in self.files:
            parent, _, name = path.rpartition("/")
            index.setdefault(parent, []).append(name)
        for rel_dir in self.dirs:
            if rel_dir:
                parent, _, name = rel_dir.rpartition("/")
                index.setdefault(parent, []).append(name)
        return {k: tuple(sorted(v)) for k, v in index.items()}

    def children(self, rel_dir: str = "") -> tuple[str, ...]:
        """目录的直接子条目名；``rel_dir=""`` 表示项目根。"""
        return self._children_index.get(rel_dir, ())

    @cached_property
    def root_entries(self) -> tuple[str, ...]:
        """根目录下的条目名（只含第一层）。"""
        return self.children("")

    @cached_property
    def _root_lower(self) -> tuple[tuple[str, str], ...]:
        return tuple((e, e.lower()) for e in self.root_entries)

    def root_startswith(self, *prefixes: str) -> str | None:
        """在根目录里按前缀（不区分大小写）找第一个条目。"""
        for wanted in prefixes:
            low = wanted.lower()
            for raw, lowered in self._root_lower:
                if lowered.startswith(low):
                    return raw
        return None

    # -- 文本 ---------------------------------------------------------------

    def text(self, rel: str) -> str | None:
        """读取项目内文本文件（带大小上限、二进制嗅探与缓存）。"""
        if rel in self._text_cache:
            return self._text_cache[rel]
        value = self._read_text(rel)
        self._text_cache[rel] = value
        return value

    def _read_text(self, rel: str) -> str | None:
        size = self.file_sizes.get(rel)
        if size is None or size > self._max_text_bytes:
            return None
        if self._text_bytes > self._max_text_total:
            return None
        path = self.root / rel
        try:
            with path.open("rb") as handle:
                # 先读 4KB 嗅探 NUL 再决定要不要读全文：仓库里常有上万个
                # 被跟踪的图片/视频，按「先读全文再判断」会白付成百 MB 的 IO。
                head = handle.read(4096)
                if b"\x00" in head:
                    return None
                raw = head + handle.read(self._max_text_bytes - len(head))
        except OSError:
            return None
        self._text_bytes += len(raw)
        return _decode(raw)

    # -- git ---------------------------------------------------------------

    @cached_property
    def git(self) -> Git:
        """只读 git 视图（首次访问才探测，不探测不 spawn）。"""
        view = Git(self.root)
        if self._injected_git_files is not None:
            # 测试注入：跳过探测与 spawn，直接把伪造名单塞进 cached_property 缓存
            view._probed = True
            view._reason = ""
            view._injected = True
            view.__dict__["ls_files"] = tuple(self._injected_git_files)
        return view
