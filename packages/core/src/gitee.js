// @allin/core — gitee 发布面查询（公开仓无需令牌）。
// 2026-09-24 强化：fetchBranchCommitStatus 区分「网络故障」与「无更新」——
// 旧版失败一律返回 null，网络故障会被静默当成「无更新」（对齐 fail-loud：
// 不静默吞掉缺失的引用）。fetchBranchCommit 保留为兼容薄封装（返回 sha|null）。

/** 查询分支最新提交：{ ok:true, commit } 或 { ok:false, error }（不抛异常）。 */
export async function fetchBranchCommitStatus(repo, branch, timeoutMs = 8000) {
  try {
    const url = `https://gitee.com/api/v5/repos/${encodeURIComponent(repo)}/branches/${encodeURIComponent(branch)}`
    const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) })
    if (!res.ok) return { ok: false, error: `gitee HTTP ${res.status}` }
    const data = await res.json()
    if (!data || !data.commit || !data.commit.sha) return { ok: false, error: 'gitee 响应缺 commit.sha' }
    return { ok: true, commit: String(data.commit.sha) }
  } catch (e) {
    return { ok: false, error: String(e?.message || e) }
  }
}

/** 兼容旧签名：成功返回 sha，任何失败返回 null。 */
export async function fetchBranchCommit(repo, branch, timeoutMs = 8000) {
  const r = await fetchBranchCommitStatus(repo, branch, timeoutMs)
  return r.ok ? r.commit : null
}
