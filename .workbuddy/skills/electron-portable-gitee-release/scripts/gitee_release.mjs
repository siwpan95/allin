// 在 Gitee 创建 Release、上传 <100MB 附件、更新发行说明，并校验下载可用。
// 用法：在装有 isomorphic-git 的 node workspace 目录下运行（本脚本只用内置 fetch，无外部依赖）。
import fs from 'fs';
import crypto from 'crypto';
import os from 'os';
import { join } from 'path';
import { spawnSync } from 'child_process';

// ---- 可调参数 ----
// 路径一律可被环境变量覆盖、默认值不含盘符（铁律 5：不把某台机器的路径写死）。
const OWNER = 'siwpan';
const REPO = 'santi-teleprompter';
const TAG = 'v1.0.0';
const NAME = 'v1.0.0 · 首个发行版';
const ASSET = process.env.RELEASE_ASSET
  ?? 'dist/SantiTeleprompter-1.0.0-portable-win-x64.7z.001'; // 单附件须 <100MB
const BODY = `## 发行说明\n\n下载后解压，双击启动即可。`;                          // Markdown 正文
// NOTE: use PortableGit 2.55.0 (the old `versions/1.2.0` tree lacks /bin/sh).
const GIT_BIN = process.env.PORTABLE_GIT_BIN
  ?? join(os.homedir(), '.workbuddy', 'binaries', 'PortableGit', 'versions', '2.55.0', 'mingw64', 'bin');

// Multiple assets: pass "path=assetName" pairs, or just paths (basename is used).
// All assets go into ONE release; each must stay under Gitee's 100MB per-file cap.
//   e.g. ['release/App-Setup-1.0.0.exe', 'release/App-1.0.0-portable.exe']
const EXTRA_ASSETS = [];
// ------------------

function getToken() {
  const r = spawnSync(GIT_BIN + '/git-credential-manager.exe', ['get'], {
    input: 'protocol=https\nhost=gitee.com\n\n', encoding: 'utf8', windowsHide: true,
    env: { ...process.env, PATH: GIT_BIN + ';' + process.env.PATH },
  });
  for (const l of (r.stdout || '').split('\n')) if (l.startsWith('password=')) return l.slice(9);
  throw new Error('Gitee token not found');
}
const token = getToken();
const api = `https://gitee.com/api/v5/repos/${OWNER}/${REPO}`;
const auth = { Authorization: 'token ' + token };

// 1) create release
const r1 = await fetch(`${api}/releases`, {
  method: 'POST',
  headers: { ...auth, 'Content-Type': 'application/json' },
  body: JSON.stringify({ tag_name: TAG, name: NAME, body: BODY, target_commitish: 'master', prerelease: false }),
});
const j1 = await r1.json();
if (!r1.ok) { console.error('create failed', r1.status, JSON.stringify(j1).slice(0, 300)); process.exit(1); }
console.log('release id:', j1.id);
const releaseId = j1.id;

// 2) attach assets (+ optional sha256 sidecar)
const assets = [[ASSET, ASSET.split('/').pop()]];
for (const p of EXTRA_ASSETS) assets.push([p, p.split('/').pop()]);

// Sidecar sha256 covering every uploaded asset.
const lines = [];
for (const [path, name] of assets) {
  lines.push(`${crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex')}  ${name}`);
}
const chk = ASSET.replace(/\.[^.]+$/, '').replace(/\.\d+$/, '') + '-installers.sha256.txt';
fs.writeFileSync(chk, lines.join('\n') + '\n');
assets.push([chk, chk.split('/').pop()]);

for (const [path, name] of assets) {
  if (fs.statSync(path).size > 100 * 1024 * 1024) {
    console.warn('WARNING: ', name, '>100MB — Gitee 会拒绝，请改用 7z 或分卷');
  }
  const fd = new FormData();
  fd.append('file', new Blob([fs.readFileSync(path)], { type: 'application/octet-stream' }), name);
  const res = await fetch(`${api}/releases/${releaseId}/attach_files?access_token=${encodeURIComponent(token)}`, { method: 'POST', body: fd });
  const j = await res.json().catch(() => ({}));
  console.log('upload', name, '->', res.status, j.id ? `(id ${j.id})` : '');
}

// 3) update notes (PATCH 必须带 tag_name)
const r3 = await fetch(`${api}/releases/${releaseId}`, {
  method: 'PATCH',
  headers: { ...auth, 'Content-Type': 'application/json' },
  body: JSON.stringify({ tag_name: TAG, name: NAME, body: BODY, prerelease: false }),
});
console.log('update notes:', r3.status);

// 4) verify
const r4 = await fetch(`${api}/releases/${releaseId}`, { headers: auth });
const j4 = await r4.json();
console.log('assets:', (j4.assets || []).map((a) => `${a.name} (${(a.size / 1024 / 1024).toFixed(1)}MB)`).join(', '));
const dl = (j4.assets || []).find((a) => /\.(7z(\.001)?|zip|exe)$/i.test(a.name));
if (dl) {
  const h = await fetch(dl.browser_download_url, { method: 'HEAD' });
  console.log('download HEAD:', h.status, h.headers.get('content-type'));
}
console.log('release url: https://gitee.com/' + OWNER + '/' + REPO + '/releases/' + TAG);
