// @allin/core — 项目注册表：platform.yaml 加载 / 校验 / 端口查表（fail-loud）。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import yaml from 'js-yaml'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.join(HERE, '..', '..', '..')

// 端口唯一事实源（机器可读版）：与 端口分配表.md 同步维护。
// 解析顺序（2026-09-24 强化：仓库可移植）：env PLATFORM_PORTS（外部端口分配表）优先；
// 缺失时回退仓内默认 registry/ports.yaml（重建自 registry/projects/*.yaml 的 port 字段，
// 新增端口仍须先查外部端口分配表再登记，仓内默认只保证查表自洽）。
export const PORTS_YAML = process.env.PLATFORM_PORTS || path.join(REPO_ROOT, 'registry', 'ports.yaml')

// path 存在性校验模式（fail-loud 的环境边界，2026-09-24 强化）：
//  - 'exists'（默认）：path 必须存在于本机——author 机器与生产环境保持原纪律；
//  - 'absolute'：仅校验绝对路径——CI / 异机跑测试用（登记的 path 指向本机外部的
//    项目目录，天然不存在；跳过存在性但保留形状校验，不让测试绑定具体机器）。
export const PATH_CHECK = process.env.PLATFORM_PATH_CHECK === 'absolute' ? 'absolute' : 'exists'

export function loadPorts(portsPath = PORTS_YAML) {
  const text = fs.readFileSync(portsPath, 'utf8')
  const doc = yaml.load(text)
  const ports = new Map()
  for (const p of doc.ports || []) ports.set(Number(p.port), p)
  return ports
}

const REQUIRED = ['id', 'name', 'category', 'version']

// gameplay 受控枚举（2026-08-25 拍板：新标签先在此登记，杜绝同玩法不同名）
export const KNOWN_GAMEPLAY = [
  'arcade', 'survivor', 'driving', 'roulette', 'snake', 'idle', 'rpg', 'card',
  'fishing', 'mahjong', 'building', 'moba', 'puzzle', 'sports', 'music',
  'visual-novel', 'sim', 'chess', 'text', 'shooting',
]

/**
 * 校验单条清单：必填字段、id 形状、launch.command、端口查表 + 归属核对。
 * @returns {string[]} 问题列表（空 = 通过）
 */
export function validateEntry(entry, ports) {
  const errors = []
  for (const k of REQUIRED) {
    if (entry[k] === undefined || entry[k] === null || entry[k] === '') errors.push(`missing required field: ${k}`)
  }
  if (entry.id && !/^[a-z0-9][a-z0-9-]*$/.test(entry.id)) errors.push(`bad id: ${entry.id}`)
  if (!entry.path) errors.push('missing path（绝对路径纪律）')
  else if (!path.isAbsolute(entry.path)) errors.push(`path 必须绝对路径: ${entry.path}`)
  else if (PATH_CHECK === 'exists' && !fs.existsSync(entry.path)) errors.push(`path 不存在: ${entry.path}`)
  if (!entry.launch || !entry.launch.command) errors.push('missing launch.command')
  if (entry.gameplay !== undefined) {
    if (!Array.isArray(entry.gameplay)) {
      errors.push('gameplay 必须为数组')
    } else {
      for (const g of entry.gameplay) {
        if (!KNOWN_GAMEPLAY.includes(g)) {
          errors.push(`gameplay 标签未登记: ${g}（受控枚举，先在 KNOWN_GAMEPLAY 登记）`)
        }
      }
    }
    if (entry.category !== 'game') {
      errors.push('非 game 类项目不应填写 gameplay 标签')
    }
  }
  if (entry.port !== undefined && entry.port !== null) {
    const p = Number(entry.port)
    if (!ports.has(p)) {
      errors.push(`port ${entry.port} 未在 ports.yaml 登记（统一端口纪律：先查表再填）`)
    } else {
      const svc = String(ports.get(p).service || '')
      if (!svc.includes(entry.id)) errors.push(`port ${entry.port} 登记服务 ${svc} 与 id ${entry.id} 不一致`)
    }
  }
  return errors
}

/**
 * 加载注册表目录（全部 *.yaml），返回 { entries, problems }。
 * 校验失败不阻塞加载：条目带 _valid=false，problems 供 --check fail-loud。
 */
export function loadRegistry(dir) {
  const ports = loadPorts()
  const entries = []
  const problems = []
  let files = []
  try {
    files = fs.readdirSync(dir).filter(f => f.endsWith('.yaml') || f.endsWith('.yml'))
  } catch (e) {
    problems.push(`registry dir 不可读: ${dir} (${e.message})`)
    return { entries, problems }
  }
  for (const f of files.sort()) {
    let entry
    try {
      entry = yaml.load(fs.readFileSync(path.join(dir, f), 'utf8'))
    } catch (e) {
      problems.push(`${f}: YAML 解析失败: ${e.message}`)
      continue
    }
    if (!entry || typeof entry !== 'object') { problems.push(`${f}: 空清单`); continue }
    const errs = validateEntry(entry, ports)
    if (errs.length) problems.push(`${f}: ${errs.join('; ')}`)
    entries.push({ ...entry, _file: f, _valid: errs.length === 0 })
  }
  const seen = new Set()
  for (const e of entries) {
    if (seen.has(e.id)) problems.push(`duplicate id: ${e.id}`)
    seen.add(e.id)
  }
  return { entries, problems, ports }
}
