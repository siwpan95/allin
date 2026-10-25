// @allin/core — gitee 发布面查询（公开仓无需令牌；失败返回 null，不抛异常）。
export async function fetchBranchCommit(repo, branch, timeoutMs = 8000) {
  try {
    const url = `https://gitee.com/api/v5/repos/${encodeURIComponent(repo)}/branches/${encodeURIComponent(branch)}`
    const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) })
    if (!res.ok) return null
    const data = await res.json()
    return data && data.commit && data.commit.sha ? String(data.commit.sha) : null
  } catch {
    return null
  }
}
