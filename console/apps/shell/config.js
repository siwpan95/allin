/**
 * allin-console · 安装态配置解析（P4）
 *
 * 为什么需要这个文件：
 *   源码态 console 位于 `<allin>/console/`，`@allin/core` 能靠 `__dirname`
 *   往上推三层找到 `platform/registry`。但**安装后** console 在
 *   `C:\Program Files\allin console\`，那里没有 allin 仓。
 *   ⇒ 运行时必须知道「本机的 allin 仓根」和「发布区根」在哪。
 *
 * 查找顺序（先具体后通用）：
 *   1. 环境变量 `ALLIN_HOME`（CI / 临时覆盖用，最高优先）
 *   2. 用户配置文件 `%APPDATA%\allin-console\config.json`
 *   3. 源码态默认：`<console 仓>/..`（即 allin 仓根）
 *   4. 注册表里查不到就报「未配置」——**不猜盘符**
 *
 * ⚠ 纪律（SPEC-003 去符盘铁律）：
 *   配置文件里存**绝对路径**是允许的（那是本机运行时配置，不是仓内清单），
 *   但仓内的 registry 清单一律禁止盘符。两者别混。
 */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))

/** 配置文件落点：%APPDATA%\allin-console\config.json */
export function configPath() {
  const base = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming')
  return path.join(base, 'allin-console', 'config.json')
}

/** 读取用户配置文件（不存在返回 null，不报错）。 */
export function readConfig() {
  const p = configPath()
  try {
    if (!fs.existsSync(p)) return null
    const raw = fs.readFileSync(p, 'utf8')
    const cfg = JSON.parse(raw)
    return typeof cfg === 'object' && cfg ? cfg : null
  } catch {
    return null
  }
}

/**
 * 写用户配置文件。原子写（先写 .tmp 再改名）——避免半截文件。
 */
export function writeConfig(cfg) {
  const p = configPath()
  fs.mkdirSync(path.dirname(p), { recursive: true })
  const tmp = p + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(cfg, null, 2) + '\n', 'utf8')
  fs.renameSync(tmp, p)
  return p
}

/**
 * 解析 allin 仓根。
 * @returns {{root: string|null, source: string, portsYaml: string|null, reposRoot: string|null}}
 */
export function resolveAllinHome() {
  // ① 环境变量优先
  const envRoot = (process.env.ALLIN_HOME || '').trim()
  if (envRoot) {
    return finish(envRoot, 'env:ALLIN_HOME')
  }
  // ② 用户配置文件
  const cfg = readConfig()
  const cfgRoot = typeof cfg?.allinHome === 'string' ? cfg.allinHome.trim() : ''
  if (cfgRoot) {
    return finish(cfgRoot, 'config')
  }
  // ③ 源码态默认：console 仓的上一级就是 allin 仓根
  //    打包后这个推导不再成立（app.asar 里没有 platform/registry），故必须靠 ①②。
  const guess = path.resolve(HERE, '..', '..', '..')
  if (fs.existsSync(path.join(guess, 'platform', 'registry', 'projects'))) {
    return finish(guess, 'repo-layout')
  }
  // ④ 打包态兜底：包内随附的 registry 快照（extraResources 打进来的）
  //    ⇒ 「装上就能看清单」，但**路径解析能力受限**（仓内 path 无法解析成真实目录），
  //       启停功能不可用 —— 要启停必须在配置里指向真实 allin 仓。
  const bundled = bundledRegistry()
  if (bundled) {
    return {
      root: null,
      source: 'bundled',
      portsYaml: bundled.portsYaml,
      reposRoot: bundled.reposRoot,
      hasRegistry: true,
      bundled: true,
    }
  }
  return { root: null, source: 'none', portsYaml: null, reposRoot: null }
}

/**
 * 找包内随附的 registry（electron-builder extraResources → resources/registry）。
 *
 * 定位方式：`process.resourcesPath` 是 Electron 提供的标准路径（打包后指向
 * `<安装目录>/resources`）；源码态没有这个变量，故只在打包态生效。
 */
function bundledRegistry() {
  const resPath = process.resourcesPath
  if (!resPath) return null
  const dir = path.join(resPath, 'registry')
  const portsYaml = path.join(dir, 'ports.yaml')
  if (!fs.existsSync(portsYaml)) return null
  const cfg = readConfig()
  const cfgRepos = typeof cfg?.reposRoot === 'string' ? cfg.reposRoot.trim() : ''
  return {
    portsYaml,
    reposRoot: cfgRepos ? path.resolve(cfgRepos) : null,
  }
}

function finish(root, source) {
  const abs = path.resolve(root)
  const portsYaml = path.join(abs, 'platform', 'registry', 'ports.yaml')
  const cfg = readConfig()
  const cfgRepos = typeof cfg?.reposRoot === 'string' ? cfg.reposRoot.trim() : ''
  // 2026-11-23：仓根搬进发布区后（`<repos>/allin`），`abs/../repos` 指向不存在的
  // `<repos>/repos`。父目录名为 repos 时，发布区根就是该父目录本身。
  const parentDir = path.resolve(abs, '..')
  const siblingRepos =
    path.basename(parentDir).toLowerCase() === 'repos'
      ? parentDir
      : path.resolve(parentDir, 'repos')
  const reposRoot = cfgRepos ? path.resolve(cfgRepos) : siblingRepos
  return {
    root: abs,
    source,
    portsYaml: fs.existsSync(portsYaml) ? portsYaml : null,
    reposRoot,
    hasRegistry: fs.existsSync(path.join(abs, 'platform', 'registry', 'projects')),
  }
}

/**
 * 把解析结果写进 core 认得的环境变量。
 *
 * core 的三个 env 钩子（platform/packages/core）：
 *   · PLATFORM_ROOT      → data/（pid 表、tasks.log）落点
 *   · PLATFORM_PORTS     → ports.yaml 路径
 *   · PLATFORM_REPOS_ROOT→ 发布区根（`repos/<仓名>` 的解析基准）
 *
 * ⚠ 必须在 `@allin/core` 被 **import 之前** 设好 —— core 在模块顶层就把
 *   PORTS_YAML / REPOS_ROOT 求值了（const），之后再设 env 无效。
 *
 * 打包态兜底（bundled）：没有真实 allin 仓，但包内带了 registry 快照 ⇒
 *   只设 PLATFORM_PORTS（指向包内 ports.yaml），**不设** PLATFORM_REPOS_ROOT
 *   —— 因为发布区不在包里，硬设一个假路径会让 core 去 stat 不存在的目录。
 *   后果：清单能列出来（148 条），但 path 解析不了 → 启停不可用。
 *   这是**如实降级**，不是伪装成完整可用。
 */
export function applyEnv() {
  const r = resolveAllinHome()
  if (r.bundled) {
    if (r.portsYaml) process.env.PLATFORM_PORTS = r.portsYaml
    // PLATFORM_ROOT：运行态数据落点。打包后没有仓 ⇒ 落到用户数据目录。
    if (!process.env.PLATFORM_ROOT) {
      process.env.PLATFORM_ROOT = path.join(
        process.env.APPDATA || process.cwd(), 'allin-console', 'data',
      )
    }
    return r
  }
  if (!r.root) return r
  process.env.PLATFORM_ROOT = path.join(r.root, 'platform')
  // ALLIN_ROOT：治理仓根。core 用它解析**仓内相对路径**（如 `platform`）。
  // 不设的话，打包态会解析到 app.asar 内 ⇒ registry 报「path 不存在」（实测）。
  if (!process.env.ALLIN_ROOT) process.env.ALLIN_ROOT = r.root
  if (r.portsYaml) process.env.PLATFORM_PORTS = r.portsYaml
  if (r.reposRoot) process.env.PLATFORM_REPOS_ROOT = r.reposRoot
  return r
}
