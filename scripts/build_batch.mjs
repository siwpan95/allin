// build_batch.mjs —— B 级批量打包（复用街机 build_all 模式，注册表驱动）。
// GUI 工具（源码含 tkinter/pygame）→ PyInstaller onefile 单 exe；CLI/纯脚本 → 便携 zip。
// 用法：node scripts/build_batch.mjs [id1 id2 ...]（缺省 = 全部 tool 类）
import path from 'node:path'
import fs from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { loadRegistry } from '@allin/core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const RELEASE = path.join(ROOT, 'release')
const BUILD = path.join(ROOT, 'build-batch')
const PY = process.env.PLATFORM_PYTHON || 'python'

const { entries } = loadRegistry(path.join(ROOT, 'registry', 'projects'))
const ids = process.argv.slice(2)
const targets = entries.filter(e => e._valid && (ids.length ? ids.includes(e.id) : e.category === 'tool'))

function isGui(entry) {
  if (!fs.existsSync(entry.path)) return false
  let has = false
  const walk = (dir, depth) => {
    if (depth > 3 || has) return
    let names
    try { names = fs.readdirSync(dir) } catch { return }
    for (const f of names) {
      const fp = path.join(dir, f)
      let st
      try { st = fs.statSync(fp) } catch { continue }
      if (st.isDirectory()) {
        if (!['.venv', 'venv', '__pycache__', '.git', 'node_modules'].includes(f)) walk(fp, depth + 1)
      } else if (f.endsWith('.py')) {
        const t = fs.readFileSync(fp, 'utf8')
        if (t.includes('import tkinter') || t.includes('import pygame')) { has = true; return }
      }
    }
  }
  walk(entry.path, 0)
  return has
}

function entryScript(entry) {
  const cmd = entry.launch.command.replace(/"/g, '')
  const m = cmd.match(/python(w)?\s+([\w./-]+\.pyw?)/)
  if (m) return m[2]
  if (/\.bat$/i.test(cmd.trim())) return 'BAT'
  const mod = cmd.match(/-m\s+([\w.]+)/)
  if (mod) return '-m:' + mod[1]
  return null
}

fs.mkdirSync(path.join(RELEASE, 'exe'), { recursive: true })
fs.mkdirSync(path.join(RELEASE, 'zip'), { recursive: true })

let ok = 0
const fails = []
for (const e of targets) {
  const script = entryScript(e)
  if (script && script !== 'BAT' && !script.startsWith('-m:') && isGui(e)) {
    const spec = path.join(BUILD, e.id + '.spec')
    fs.mkdirSync(BUILD, { recursive: true })
    const datas = fs.readdirSync(e.path).filter(f => {
      const fp = path.join(e.path, f)
      return fs.statSync(fp).isFile() && !/\.(py|pyc|spec)$/.test(f)
    }).map(f => '(' + JSON.stringify(path.join(e.path, f)) + ", '.')")
    const escEntry = path.join(e.path, script).replace(/\\/g, '/')
    const escPath = e.path.replace(/\\/g, '/')
    const specBody = [
      'a = Analysis(',
      '    [' + JSON.stringify(escEntry) + '],',
      '    pathex=[' + JSON.stringify(escPath) + '],',
      '    binaries=[],',
      '    datas=[' + datas.join(', ') + '],',
      '    hiddenimports=[],',
      '    hookspath=[],',
      '    hooksconfig={},',
      '    runtime_hooks=[],',
      "    excludes=['torch', 'cv2', 'moviepy', 'sqlalchemy'],",
      '    noarchive=False,',
      ')',
      'pyz = PYZ(a.pure)',
      "exe = EXE(pyz, a.scripts, exclude_binaries=True, name='" + e.id + "', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)",
    ].join('\n') + '\n'
    fs.writeFileSync(spec, specBody)
    const r = spawnSync(PY, ['-m', 'PyInstaller', spec, '--noconfirm', '--distpath', path.join(RELEASE, 'exe'), '--workpath', path.join(BUILD, e.id)], { cwd: ROOT, encoding: 'utf8', timeout: 1800000 })
    const exe = path.join(RELEASE, 'exe', e.id + '.exe')
    // PyInstaller onefile 在本机把产物落在 workpath/<id>/<id>.exe（已知怪癖）→ 查找并复制到 release/exe
    if (r.status === 0 && !fs.existsSync(exe)) {
      const walk = (dir, depth) => {
        if (depth > 3) return
        let names
        try { names = fs.readdirSync(dir) } catch { return }
        for (const f of names) {
          const fp = path.join(dir, f)
          let st
          try { st = fs.statSync(fp) } catch { continue }
          if (st.isDirectory()) walk(fp, depth + 1)
          else if (f === e.id + '.exe') fs.copyFileSync(fp, exe)
        }
      }
      walk(path.join(BUILD, e.id), 0)
    }
    if (r.status === 0 && fs.existsSync(exe)) {
      console.log('[exe OK] ' + e.id + '  ' + (fs.statSync(exe).size / 1e6).toFixed(1) + ' MB')
      ok++
    } else {
      console.log('[exe FAIL] ' + e.id + ' status=' + r.status + ' err=' + String(r.error || '') + ' sig=' + String(r.signal || ''))
      console.log(String(r.stderr || r.stdout || '').slice(-400))
      fails.push(e.id)
    }
  } else if (script) {
    const zipName = path.join(RELEASE, 'zip', e.id + '-portable.zip')
    const pycode = [
      'import zipfile, os',
      'root = ' + JSON.stringify(e.path),
      'out = ' + JSON.stringify(zipName),
      "with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:",
      '    for dp, dns, fns in os.walk(root):',
      "        dns[:] = [d for d in dns if d not in {'.venv','venv','__pycache__','.git','.pytest_cache','node_modules','build','dist','release'}]",
      '        for f in fns:',
      '            fp = os.path.join(dp, f)',
      '            z.write(fp, os.path.relpath(fp, root))',
    ].join('\n')
    const r = spawnSync(PY, ['-c', pycode], { cwd: ROOT, encoding: 'utf8', timeout: 600000 })
    if (r.status === 0 && fs.existsSync(zipName)) {
      console.log('[zip OK] ' + e.id + '  ' + (fs.statSync(zipName).size / 1e6).toFixed(1) + ' MB')
      ok++
    } else {
      console.log('[zip FAIL] ' + e.id)
      fails.push(e.id)
    }
  }
}
console.log('== 完成：' + ok + ' 成功 / ' + fails.length + ' 失败' + (fails.length ? '：' + fails.join(',') : ''))
process.exit(fails.length ? 1 : 0)
