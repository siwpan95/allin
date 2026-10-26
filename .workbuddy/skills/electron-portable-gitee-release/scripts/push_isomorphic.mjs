// 通过 isomorphic-git 把本地仓库推送到 Gitee，并用 Gitee API 校验远端 HEAD。
// 用法：在装有 isomorphic-git 的 node workspace 目录下运行，或修改 IG 为绝对 file:// 路径。
// 令牌从 Windows 凭据管理器读取，仅在内存中使用，不落盘。
import git from 'isomorphic-git';
import http from 'isomorphic-git/http/node';
import { promises as fsp } from 'fs';
import os from 'os';
import { join } from 'path';
import { spawnSync } from 'child_process';

// ---- 可调参数 ----
// 路径一律可被环境变量覆盖、默认值不含盘符（铁律 5：不把某台机器的路径写死）。
const DIR = process.env.REPO_DIR ?? process.cwd();          // 本地仓库
const REMOTE = 'origin';
const REF = 'master';
const OWNER = 'siwpan';
const REPO = 'santi-teleprompter';
// NOTE: use PortableGit 2.55.0. The old `versions/1.2.0` tree lacks /bin/sh and
// cannot spawn shell hooks / credential helpers reliably.
const GIT_BIN = process.env.PORTABLE_GIT_BIN
  ?? join(os.homedir(), '.workbuddy', 'binaries', 'PortableGit', 'versions', '2.55.0', 'mingw64', 'bin');
const FORCE = false;                                       // 需要覆盖远端历史时置 true
// ------------------

const fs = {
  promises: fsp,
  readFile: (...a) => fsp.readFile(...a), writeFile: (...a) => fsp.writeFile(...a),
  unlink: (...a) => fsp.unlink(...a), readdir: (...a) => fsp.readdir(...a),
  mkdir: (...a) => fsp.mkdir(...a), rmdir: (...a) => fsp.rmdir(...a),
  stat: (...a) => fsp.stat(...a), lstat: (...a) => fsp.lstat(...a),
  readlink: (...a) => fsp.readlink(...a), symlink: (...a) => fsp.symlink(...a),
};

function getToken() {
  const r = spawnSync(GIT_BIN + '/git-credential-manager.exe', ['get'], {
    input: 'protocol=https\nhost=gitee.com\n\n', encoding: 'utf8', windowsHide: true,
    env: { ...process.env, PATH: GIT_BIN + ';' + process.env.PATH },
  });
  for (const l of (r.stdout || '').split('\n')) if (l.startsWith('password=')) return l.slice(9);
  throw new Error('Gitee token not found in Windows Credential Manager');
}
const token = getToken();
const auth = () => ({ username: 'oauth2', password: token });

const local = await git.resolveRef({ fs, dir: DIR, ref: REF });
console.log('local', REF, local);
const res = await git.push({ fs, http, dir: DIR, remote: REMOTE, ref: REF, force: FORCE, onAuth: auth });
console.log('push:', JSON.stringify(res.refs));

const r = await fetch(`https://gitee.com/api/v5/repos/${OWNER}/${REPO}/branches/${REF}`, {
  headers: { Authorization: 'token ' + token },
});
const j = await r.json();
console.log('remote', REF, j.commit && j.commit.sha, j.commit && j.commit.sha === local ? 'VERIFIED' : 'MISMATCH');
