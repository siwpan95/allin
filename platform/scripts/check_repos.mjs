// check_repos.mjs —— 发布区 repos 治理核验（本机 ⇄ 远端双向核对）。exit 0 = 全部通过。
//
// 为什么需要它： loadRegistry 的存在性校验只答「path 在本机存不存在」，答不了两个真问题：
//   ① publish.repo 指向的远端仓**还在不在**（治理仓重写 / 删仓后旧地址无重定向，直连 404）；
//   ② 本机目录名与远端仓名**是否同名**（可用 <目录旧名> 蒙混过校验，锚点却是死的）。
// 活样本：2026-10-21 particle 删仓重建为 particlefx，本机目录仍叫 particle，
//        存在性校验一路绿灯，publish.repo 却已指向 404。
// ⇒ 本脚本补上远端实测面，**不替代 check.mjs，是它的补充纵深**。
//
// 用法：
//   node scripts/check_repos.mjs            # 本机 + 远端双向核验（需网络）
//   PLATFORM_REPOS_OFFLINE=1 node scripts/check_repos.mjs   # 离线降级，仅本机面
//   PLATFORM_REPOS_ROOT=<发布区根> node scripts/check_repos.mjs
//
// 严重度：发现 error 一律 exit 1（fail-loud）；远端 API 不可用时降级为 warn，
//         不计入 error —— 网络抖动不是治理对象的错，但要看得见。
import path from "node:path"
import fs from "node:fs"
import { fileURLToPath } from "node:url"
import { loadRegistry, REPOS_ROOT } from "@allin/core"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(__dirname, "..", "registry", "projects")
const OWNER = process.env.PLATFORM_GITEE_OWNER || "siwpan"
const OFFLINE = process.env.PLATFORM_REPOS_OFFLINE === "1"
const API = "https://gitee.com/api/v5"

// ── 远端实测：匿名只读，不需要令牌（与 tools/build_portfolio.py 同口径）──────
// ⚠️ 务必用 type=all：实测 type=public 会返回空列表，误判成「拿不到数据」。
async function fetchRemote() {
  const out = []
  for (let page = 1; page <= 5; page++) {
    const url = `${API}/users/${OWNER}/repos?type=all&sort=full_name&per_page=100&page=${page}`
    const res = await fetch(url, {
      headers: { "User-Agent": "allin-repos-governance" },
      signal: AbortSignal.timeout(30000),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const batch = await res.json()
    if (!Array.isArray(batch) || batch.length === 0) break
    out.push(...batch)
    if (batch.length < 100) break
  }
  return new Map(out.map(r => [String(r.path).toLowerCase(), { path: r.path, private: !!r.private }]))
}

const errors = []
const warns = []

const { entries, problems } = loadRegistry(REGISTRY)

// ① 本机面：沿用 loadRegistry 的既有校验（path 存在性 / 盘符 / 必填项）
for (const p of problems) errors.push(`[本机] ${p}`)

let remote = null
if (!OFFLINE) {
  try {
    remote = await fetchRemote()
    console.log(`[repos] 远端实测：${OWNER} 共 ${remote.size} 个仓库`)
  } catch (e) {
    warns.push(`[远端] 取不到 Gitee 仓库清单（${e.message}），本轮降级为仅本机核验`)
  }
} else {
  warns.push("[远端] PLATFORM_REPOS_OFFLINE=1，本轮跳过远端实测")
}

if (remote) {
  for (const e of entries) {
    const repo = e.publish && e.publish.repo            // 形如 siwpan/xxx
    const p = e.path || ""

    // ② publish.repo 是否还活着
    if (repo) {
      const name = String(repo).split("/").pop()
      if (!remote.has(name.toLowerCase())) {
        errors.push(`[远端] ${e.id}: publish.repo=${repo} 在远端不存在（疑似删仓/改名 → 校验锚点）`)
      } else {
        // ③ 本机目录名 vs 远端仓名是否同名（particle 类错位的唯一抓法）
        const m = p.match(/^repos\/([^/]+)/)
        if (m && m[1].toLowerCase() !== name.toLowerCase()) {
          errors.push(
            `[错位] ${e.id}: path 目录名 "${m[1]}" ≠ publish.repo 仓名 "${name}"` +
            `（本机目录仍在旧名，锚点已漂）`
          )
        }
      }
    }

    // path 存在性已被 loadRegistry 覆盖（problems），此处不重复报，避免同一缺陷出现两次
  }
}

// 输出
for (const w of warns) console.warn("[warn] " + w)
if (errors.length) {
  console.error(`\n[check:repos] 发现 ${errors.length} 项待治理：`)
  for (const e of errors) console.error("  - " + e)
  console.error(`\n提示：远端仓若已更名，先在本文件跑通后同步修 path / publish.repo，` +
                `再跑 node scripts/check_repos.mjs 复验。`)
  process.exit(1)
}
console.log(`[check:repos] 通过：${entries.length} 条清单的本机/远端锚点一致` +
            (remote ? "" : "（本轮未做远端实测）"))
process.exit(0)
