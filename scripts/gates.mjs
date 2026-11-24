// 门禁套件的入口薄壳 —— 从**已安装的 allin-governance 包**里找 run.ts 并执行。
//
// 为什么需要这一层（2026-11-25 公共核提仓）：
//   套件源码已迁至独立仓 allin-governance，本仓不再有 tools/gate/governance/run.ts。
//   npm 脚本若写 `node "$(python -c …)"`，在 Windows 的 cmd.exe 下 `$()` 不生效；
//   所以用 node 解析路径再 spawn，跨平台一致。
//
// 用法：node scripts/gates.mjs [--selfcheck-all|--no-profile|…]
import { spawnSync } from "node:child_process";

// 解释器优先级：显式 env → 仓内 .venv（装包的那个）→ PATH 里的 python
import { existsSync } from "node:fs";
import { join } from "node:path";

const venvPy = join(process.cwd(), ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const PY = process.env.ALLIN_PYTHON
  || (existsSync(venvPy) ? venvPy : (process.platform === "win32" ? "python" : "python3"));
const FIND = [
  "-c",
  "import allin_governance,os,sys; sys.stdout.write(os.path.join(os.path.dirname(allin_governance.__file__),'_gatesuite','run.ts'))",
];

const found = spawnSync(PY, FIND, { encoding: "utf8" });
const runTs = (found.stdout || "").trim();
if (found.status !== 0 || !runTs) {
  console.error(
    "[gates] 找不到门禁套件：allin-governance 未安装？\n" +
      "  先 `pip install allin-governance`（公共核已独立成仓），或用 ALLIN_PYTHON 指定带该包的解释器。"
  );
  if (found.stderr) console.error(found.stderr.trim());
  process.exit(3);
}

const r = spawnSync("node", [runTs, ...process.argv.slice(2)], { stdio: "inherit" });
process.exit(r.status === null ? 1 : r.status);
