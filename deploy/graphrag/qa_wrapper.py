#!/usr/bin/env python3
# qa_wrapper.py —— allin 知识库 QA 降级封装（零外部依赖、可跑）。
#
# 把 qa.yaml 里描述的三档降级（full / offline / readonly）从纸面配置变成可执行路由：
#   full     —— 需 GRAPHRAG_API_KEY + facts.sqlite（由外部 GraphRAG 索引产出）；
#              缺任一项即自动降级，绝不静默假装 full。
#   offline  —— facts.sqlite（结构化真身）+ docs/ 全文扫描（叙述层，确定性 BM25 近似）。
#   readonly —— facts.json（结构化真身，JSON Schema 校验后）+ 内存全文索引。
#
# 治理边界（2026-11-10）：本脚本不引入 LLM 运行时、不发起任何网络调用。它只负责
# 「这份查询该检索哪份真身、命中哪个降级档位」，并把档位如实标注在返回里。答案的
# 自然语言生成由仓外编排层完成——本仓 MCP 工具面（docs.search / facts.query 等）
# 是确定性降级终点。
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / 'docs'
FACTS_JSON = REPO / 'facts' / 'facts.json'
FACTS_SQLITE = REPO / 'facts' / 'facts.sqlite'   # 派生库，可能不存在
QA_YAML = Path(__file__).resolve().parent / 'qa.yaml'


def _read_mode_from_yaml() -> str:
    """极简解析 qa.yaml 顶层 mode（避免对 PyYAML 的强依赖；qa.yaml 顶层只有标量）。"""
    try:
        text = QA_YAML.read_text(encoding='utf-8')
    except OSError:
        return 'auto'
    m = re.search(r'^mode:\s*(\w+)', text, re.MULTILINE)
    return m.group(1) if m else 'auto'


def pick_mode(requested: str) -> tuple[str, bool]:
    """返回 (实际档位, 是否因资源缺失而降级)。"""
    if requested in ('full', 'offline', 'readonly'):
        configured = requested
    else:
        configured = _read_mode_from_yaml()

    if configured == 'full':
        have_key = bool(__import__('os').environ.get('GRAPHRAG_API_KEY'))
        have_index = FACTS_SQLITE.exists()
        if have_key and have_index:
            return 'full', False
        # 缺资源：诚实降级，不假装 full
        if have_index:
            return 'offline', True
        return 'readonly', True

    if configured == 'offline' and not FACTS_SQLITE.exists():
        return 'readonly', True
    return configured, False


def _ok(b: bytes) -> str:
    return b.decode('utf-8', 'replace')


def _bm25_score(query_terms: list[str], text: str) -> float:
    """极简 BM25 近似：命中词数 / 长度，确定性、可审计（不依赖向量库）。"""
    hay = text.lower()
    if not hay:
        return 0.0
    hits = sum(hay.count(t.lower()) for t in query_terms)
    return hits / (1.0 + len(text) / 200.0)


def search_docs(query: str, limit: int = 8) -> list[dict]:
    """offline 档叙述层检索：docs/ 全文扫描 + BM25 近似，返回 file:line 片段。"""
    terms = [t for t in re.split(r'\s+', query.strip()) if t]
    if not terms:
        return []
    out = []
    for p in sorted(DOCS.rglob('*.md')):
        # 跳过历史冻结树（与门禁口径一致）
        if 'md/' in str(p) or '.workbuddy' in str(p):
            continue
        try:
            lines = p.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if any(t.lower() in line.lower() for t in terms):
                out.append({'path': str(p.relative_to(REPO)).replace('\\', '/'),
                            'line': i, 'snippet': line.strip()[:160],
                            'score': _bm25_score(terms, line)})
    out.sort(key=lambda r: r['score'], reverse=True)
    return out[:limit]


def search_facts_json(query: str, limit: int = 8) -> list[dict]:
    """readonly 档结构化检索：facts.json 内存全文索引。"""
    if not FACTS_JSON.exists():
        return []
    try:
        data = json.loads(FACTS_JSON.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    blob = json.dumps(data, ensure_ascii=False)
    terms = [t for t in re.split(r'\s+', query.strip()) if t]
    if not terms:
        return []
    # facts.json 可能很大，按顶层键切片检索
    results = []
    if isinstance(data, dict):
        for key, val in data.items():
            chunk = json.dumps({key: val}, ensure_ascii=False)
            if any(t.lower() in chunk.lower() for t in terms):
                results.append({'path': 'facts/facts.json', 'key': key,
                                'snippet': chunk[:160], 'score': _bm25_score(terms, chunk)})
    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


def search_facts_sqlite(query: str, limit: int = 8) -> list[dict]:
    """offline 档结构化检索：facts.sqlite 派生库（若存在）。"""
    if not FACTS_SQLITE.exists():
        return []
    try:
        con = sqlite3.connect(str(FACTS_SQLITE))
        cur = con.cursor()
        like = '%' + query.replace('%', '') + '%'
        rows = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        results = []
        for (tbl,) in rows:
            try:
                for row in cur.execute(
                    f"SELECT * FROM '{tbl}' WHERE 0=1"  # 占位，避免无 where 全扫；实际用下方探测列
                ):
                    pass
            except sqlite3.Error:
                pass
            try:
                col = cur.execute(f"PRAGMA table_info('{tbl}')").fetchone()
                if col:
                    cid = col[1]
                    for r in cur.execute(
                        f"SELECT '{tbl}', {cid} FROM '{tbl}' WHERE {cid} LIKE ? LIMIT ?",
                        (like, limit),
                    ):
                        results.append({'path': f'facts.sqlite#{tbl}', 'snippet': str(r[1])[:160]})
            except sqlite3.Error:
                continue
        con.close()
        return results[:limit]
    except sqlite3.Error:
        return []


def answer(query: str, mode: str = 'auto') -> dict:
    chosen, degraded = pick_mode(mode)
    structured, narrative = [], []
    if chosen in ('offline', 'full') and FACTS_SQLITE.exists():
        structured = search_facts_sqlite(query)
    if chosen == 'readonly' or not structured:
        structured = search_facts_json(query) or structured
    if chosen in ('offline', 'full'):
        narrative = search_docs(query)

    return {
        'query': query,
        'mode': chosen,
        'degraded': degraded,
        'disclose_in_response': f'knowledge_index={chosen}' if degraded else None,
        'structured_hits': len(structured),
        'narrative_hits': len(narrative),
        'structured': structured[:5],
        'narrative': narrative[:5],
        'no_evidence_policy': '拒答（不编造）；数字类主张须由 facts 真身复算',
    }


def _selfcheck() -> int:
    code = 0
    for mode in ('full', 'offline', 'readonly', 'auto'):
        try:
            res = answer('端口 注册表 门禁', mode=mode)
            assert 'mode' in res and 'structured_hits' in res
            print(f"  selfcheck {mode}: mode={res['mode']} degraded={res['degraded']} "
                  f"struct={res['structured_hits']} narr={res['narrative_hits']}")
        except Exception as e:  # noqa: BLE001
            print(f"  selfcheck {mode}: FAILED {type(e).__name__}: {e}")
            code = 1
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description='allin 知识库 QA 降级封装（零依赖）')
    ap.add_argument('query', nargs='?', help='查询文本')
    ap.add_argument('--mode', default='auto',
                    choices=['auto', 'full', 'offline', 'readonly'])
    ap.add_argument('--selfcheck', action='store_true', help='跑三档降级自检后退出')
    args = ap.parse_args()
    if args.selfcheck or not args.query:
        if args.selfcheck:
            return _selfcheck()
        ap.print_help()
        return 0
    print(json.dumps(answer(args.query, args.mode), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
