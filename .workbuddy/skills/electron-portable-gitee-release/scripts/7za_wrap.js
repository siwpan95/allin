// 7za wrapper: tolerates the macOS symlink privilege failure when app-builder
// extracts the winCodeSign archive, and auto-confirms overwrite prompts.
//
// Why this exists
// ---------------
// electron-builder's `app-builder.exe` shells out to 7za to extract
// winCodeSign-2.6.0.7z, which contains macOS *symlinks*
// (darwin/10.12/lib/libcrypto.dylib, libssl.dylib). Creating symlinks on Windows
// requires SeCreateSymbolicLinkPrivilege; in a sandbox / non-elevated account it
// fails, 7za exits 2, and app-builder treats that as fatal (it retries 3x, then
// the whole build dies with exit 1).
//
// app-builder normally invokes 7za by ABSOLUTE path, so PATH tricks alone do not
// work. The hook is `USE_SYSTEM_7ZA=true`: then 7zip-bin's getPath7za() returns
// the bare string "7za", which resolves through PATH — and this wrapper is what
// PATH finds. See SKILL.md "流程 D · 卡点 1".
//
// Setup
// -----
//   1. Rename the real binary:  7zip-bin/win/x64/7za.exe  ->  7za_real.exe
//      (must rename: .EXE precedes .CMD in PATHEXT, so a same-named .exe would win)
//   2. Put this file + 7za.cmd next to each other in a dir at the FRONT of PATH.
//   3. Build with: USE_SYSTEM_7ZA=true  SZA_PATH=7za
//
// Exit code contract: return 0 when the retry produces a usable extraction
// (detected by the presence of rcedit-x64.exe), so app-builder continues.
const { spawnSync } = require('child_process')
const path = require('path')
const fs = require('fs')

// ---- 可调参数 ----
// Real 7za binary. Override with SANTI_REAL_7ZA if your layout differs.
const REAL = process.env.SANTI_REAL_7ZA ||
  path.join(__dirname, '7za_real.exe')
// Invocation log (handy to prove the wrapper is actually being used). Set to '' to disable.
const LOG = process.env.SANTI_7ZA_LOG || ''
// ------------------

if (LOG) {
  try {
    fs.appendFileSync(LOG, new Date().toISOString() + ' ARGS: ' +
      JSON.stringify(process.argv.slice(2)) + '\n')
  } catch (e) {}
}

const rawArgs = process.argv.slice(2)
// Always answer yes to overwrite prompts; app-builder runs headless and would hang.
const args = rawArgs.some(a => a === '-y' || a === '-y-') ? rawArgs : rawArgs.concat(['-y'])

function run(a) {
  const r = spawnSync(REAL, a, { encoding: 'buffer' })
  return {
    status: r.status === null ? 1 : r.status,
    out: (r.stdout || Buffer.alloc(0)),
    err: (r.stderr || Buffer.alloc(0)),
  }
}

function emit(b) { try { process.stdout.write(b) } catch (e) {} }
function emitErr(b) { try { process.stderr.write(b) } catch (e) {} }

const first = run(args)
emit(first.out)
emitErr(first.err)

if (first.status === 0) process.exit(0)

// Was this an extraction of the winCodeSign archive, failing on symlinks?
const joined = args.join(' ')
const isExtract = args.some(a => a === 'x' || a === 'e')
const mentionsWinCodeSign = /winCodeSign/i.test(joined)
const combined = (first.out.toString('latin1') + first.err.toString('latin1'))
const symlinkIssue = /symbolic link/i.test(combined) || /特权/.test(combined) ||
  /privilege/i.test(combined)

if (isExtract && mentionsWinCodeSign && symlinkIssue) {
  let arc = null
  let outDir = null
  for (const a of args) {
    if (/\.7z$/i.test(a) && !a.startsWith('-')) arc = a
    if (a.startsWith('-o')) outDir = a.slice(2)
  }
  if (arc) {
    // Drop -snld (store symlinks as links) and exclude the darwin tree so no
    // symlink is ever attempted. Everything Windows needs is still extracted.
    const retry = args.filter(a => !/^-snld$/.test(a))
    retry.push('-x!darwin\\10.12\\lib\\libcrypto.dylib')
    retry.push('-x!darwin\\10.12\\lib\\libssl.dylib')
    const second = run(retry)
    emit(second.out)
    emitErr(second.err)
    // Treat the artifact as usable if the Windows-side tools are present, even
    // if 7za still reported a non-zero status for the skipped entries.
    if (outDir && fs.existsSync(path.join(outDir, 'rcedit-x64.exe'))) process.exit(0)
    process.exit(second.status)
  }
}

process.exit(first.status)
