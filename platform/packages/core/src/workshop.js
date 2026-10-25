// @allin/core — 单机创意工坊（P3.5：真实 git pull）
// 订阅 = clone 发布面到 workshop-copies/<id>；更新 = git pull（失败回退 fetch+reset）；
// 回滚 = checkout 历史提交；退订 = 删除副本。每个动作写任务日志（日志即事实源）。
// 项目原目录永不被触碰（独立更新纪律）；fetcher/gitUrl 可注入（测试用本地 bare 仓）。
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { DATA_DIR, PLATFORM_ROOT, logTask } from './launch.js'
import { fetchBranchCommitStatus } from './gitee.js'

const STATE_FILE = path.join(DATA_DIR, 'workshop.json')
export const COPIES_DIR = path.join(PLATFORM_ROOT, 'workshop-copies')

function loadState() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'))
  } catch {
    return { subscriptions: {} }
  }
}

function saveState(state) {
  fs.mkdirSync(DATA_DIR, { recursive: true })
  // 原子写（2026-09-24 Phase 1 升级，对齐 running.json 同款 durable 纪律）：
  // temp + fsync + rename，杜绝半截 JSON；与 launch.js writeDurable 同语义
  const tmp = STATE_FILE + '.' + process.pid + '.tmp'
  const data = JSON.stringify(state, null, 2)
  const fd = fs.openSync(tmp, 'w')
  try { fs.writeSync(fd, data); fs.fsyncSync(fd) } finally { fs.closeSync(fd) }
  fs.renameSync(tmp, STATE_FILE)
}

function repoUrl(repo, override) {
  return override || `https://gitee.com/${repo}.git`
}

function copyDir(id) {
  return path.join(COPIES_DIR, id)
}

function git(args, timeout = 120000) {
  return execFileSync('git', args, { encoding: 'utf8', timeout, stdio: ['ignore', 'pipe', 'pipe'] }).trim()
}

function cloneRepo(repo, branch, gitUrl, dest) {
  fs.rmSync(dest, { recursive: true, force: true })
  fs.mkdirSync(COPIES_DIR, { recursive: true })
  git(['clone', '--quiet', '--depth', '1', '--single-branch', '--branch', branch, repoUrl(repo, gitUrl), dest])
}

function pullRepo(dest, branch) {
  try {
    git(['-C', dest, 'pull', '--quiet', '--ff-only'])
  } catch {
    // 历史被重写等非快进场景：回退到远端状态
    git(['-C', dest, 'fetch', '--quiet', 'origin', branch])
    git(['-C', dest, 'reset', '--hard', 'origin/' + branch])
  }
}

function headCommit(dest) {
  return git(['-C', dest, 'rev-parse', 'HEAD'])
}

/** 目录 = 注册表中声明 publish 的项目（gitee 公开仓，铁律 0）。 */
export function listWorkshop(entries) {
  const state = loadState()
  const catalog = entries
    .filter(e => e.publish && e.publish.repo)
    .map(e => ({
      id: e.id,
      name: e.name,
      category: e.category,
      version: e.version,
      repo: e.publish.repo,
      branch: e.publish.branch || 'master',
      subscribed: Boolean(state.subscriptions[e.id]),
      subscribedAt: state.subscriptions[e.id]?.subscribedAt || null,
      commit: state.subscriptions[e.id]?.commit || null,
      history: state.subscriptions[e.id]?.history || [],
      copyExists: fs.existsSync(path.join(copyDir(e.id), '.git')),
      updateAvailable: Boolean(state.subscriptions[e.id]?.pendingUpdate),
      pendingCommit: state.subscriptions[e.id]?.pendingCommit || null,
    }))
  return { catalog, subscriptions: state.subscriptions }
}

/** 订阅：clone 发布面副本并记录当前提交。 */
export async function subscribe(id, entry, opts = {}) {
  if (!entry || !entry.publish || !entry.publish.repo) {
    return { ok: false, reason: 'no-publish-info', id }
  }
  const branch = entry.publish.branch || 'master'
  const fetcher = opts.fetcher || fetchBranchCommitStatus
  const raw = await fetcher(entry.publish.repo, branch)
  // 兼容两种 fetcher 形态：直接返回 sha 字符串（旧/测试注入）或 { ok, commit }（status 版）
  const remote = typeof raw === 'string' ? raw : (raw && raw.ok ? raw.commit : null)
  let commit = null
  let cloneError = null
  try {
    cloneRepo(entry.publish.repo, branch, opts.gitUrl, copyDir(id))
    commit = headCommit(copyDir(id))
  } catch (e) {
    cloneError = String(e.message || e).slice(0, 200)
  }
  const state = loadState()
  state.subscriptions[id] = {
    version: entry.version,
    source: entry.publish.repo + '#' + branch,
    commit,
    history: [],
    pendingUpdate: false,
    pendingCommit: null,
    subscribedAt: new Date().toISOString(),
  }
  saveState(state)
  logTask({
    project: id, action: 'workshop-subscribe',
    source: state.subscriptions[id].source,
    commit: commit || undefined, clone_error: cloneError || undefined, remote: remote || undefined,
  })
  return { ok: true, id, commit, cloneError }
}

export function unsubscribe(id) {
  const state = loadState()
  if (!state.subscriptions[id]) {
    return { ok: false, reason: 'not-subscribed', id }
  }
  delete state.subscriptions[id]
  saveState(state)
  fs.rmSync(copyDir(id), { recursive: true, force: true })
  logTask({ project: id, action: 'workshop-unsubscribe' })
  return { ok: true, id }
}

/** 检查更新：比对 gitee 最新提交与订阅记录。
 *  2026-09-24 强化：网络故障不再伪装成「无更新」——checkError 显式带回，门户可显示。 */
export async function checkUpdate(id, entry, fetcher = fetchBranchCommitStatus) {
  const state = loadState()
  const sub = state.subscriptions[id]
  if (!sub || !entry?.publish?.repo) return { ok: false, reason: 'not-subscribed', id }
  const branch = entry.publish.branch || 'master'
  const r = await fetcher(entry.publish.repo, branch)
  if (!r.ok) {
    return { ok: true, id, current: sub.commit, latest: null, updateAvailable: false, checkError: r.error }
  }
  const latest = r.commit
  return { ok: true, id, current: sub.commit, latest, updateAvailable: Boolean(latest && sub.commit && latest !== sub.commit) }
}

/** 更新：真实 git pull 副本，旧提交入 history（可回滚）。 */
export async function update(id, entry, opts = {}) {
  const state = loadState()
  const sub = state.subscriptions[id]
  if (!sub || !entry?.publish?.repo) return { ok: false, reason: 'not-subscribed', id }
  const branch = entry.publish.branch || 'master'
  try {
    if (!fs.existsSync(path.join(copyDir(id), '.git'))) {
      cloneRepo(entry.publish.repo, branch, opts.gitUrl, copyDir(id))
    } else {
      pullRepo(copyDir(id), branch)
    }
  } catch (e) {
    return { ok: false, reason: 'pull-failed', id, error: String(e.message || e).slice(0, 200) }
  }
  const latest = headCommit(copyDir(id))
  if (sub.commit === latest) return { ok: true, id, changed: false, commit: latest }
  sub.history.push({ commit: sub.commit, version: sub.version, at: new Date().toISOString() })
  // history 上限（2026-09-24 强化）：只留最近 50 代可回滚点，防 state 无限膨胀
  if (sub.history.length > 50) sub.history.splice(0, sub.history.length - 50)
  sub.commit = latest
  sub.pendingUpdate = false
  sub.pendingCommit = null
  sub.updatedAt = new Date().toISOString()
  saveState(state)
  logTask({ project: id, action: 'workshop-update', from: sub.history[sub.history.length - 1].commit, to: latest })
  return { ok: true, id, changed: true, commit: latest }
}

/** 回滚：副本 checkout 至 history 最近一次提交。 */
export function rollback(id) {
  const state = loadState()
  const sub = state.subscriptions[id]
  if (!sub) return { ok: false, reason: 'not-subscribed', id }
  const prev = sub.history.pop()
  if (!prev || !prev.commit) return { ok: false, reason: 'no-history', id }
  const current = sub.commit
  try {
    if (fs.existsSync(path.join(copyDir(id), '.git'))) {
      // 2026-09-24 强化：浅克隆（--depth 1）下旧提交可能不在对象库——
      // 普通 fetch 失败时升级 --unshallow；仍失败（历史重写）再按指名 SHA 抓取
      try {
        git(['-C', copyDir(id), 'fetch', '--quiet', 'origin'])
      } catch {
        git(['-C', copyDir(id), 'fetch', '--quiet', '--unshallow', 'origin'])
      }
      try {
        git(['-C', copyDir(id), 'reset', '--hard', prev.commit])
      } catch {
        // 旧提交不在对象库（浅克隆/历史重写）：先 unshallow 补全历史，仍不行按指名 SHA 抓
        try {
          git(['-C', copyDir(id), 'fetch', '--quiet', '--unshallow', 'origin'])
        } catch {
          git(['-C', copyDir(id), 'fetch', '--quiet', 'origin', prev.commit])
        }
        git(['-C', copyDir(id), 'reset', '--hard', prev.commit])
      }
    }
  } catch (e) {
    return { ok: false, reason: 'checkout-failed', id, error: String(e.message || e).slice(0, 200) }
  }
  sub.commit = prev.commit
  sub.version = prev.version
  sub.pendingUpdate = false
  sub.pendingCommit = null
  saveState(state)
  logTask({ project: id, action: 'workshop-rollback', from: current, to: prev.commit })
  return { ok: true, id, commit: prev.commit }
}

/** 审计：workshop 相关任务日志尾部（JSONL → JSON 数组）。 */
export function auditWorkshop(limit = 50) {
  const file = path.join(DATA_DIR, 'tasks.log')
  let lines = []
  try {
    lines = fs.readFileSync(file, 'utf8').trim().split('\n')
  } catch { /* 无日志 */ }
  return lines
    .filter(l => l.includes('workshop-'))
    .slice(-limit)
    .map(l => { try { return JSON.parse(l) } catch { return { raw: l } } })
}
