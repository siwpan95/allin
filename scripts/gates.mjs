// 门禁套件的入口薄壳 —— 从**已安装的 allin-governance 包**里找 run.ts 并执行。
//
// 为什么需要这一层（2026-11-25 公共核提仓）：
//   套件源码已迁至独立仓 allin-governance，本仓不再有 tools/gate/governance/run.ts。
//   npm 脚本若写 `node "$(python -c …)"`，在 Windows 的 cmd.exe 下 `$()` 不生效；
//   所以用 node 解析路径再 spawn，跨平台一致。
//
// 用法：node scripts/gates.mjs [--selfcheck-all|--no-profile|--root <仓根>|…]
//
// 2026-11-25 修两处「靠 process.cwd() 猜」的缺陷（提仓后第一现场）：
//   1. **解释器与仓根都由脚本自身位置推导**，不再取 cwd。此前 `cd /tmp &&
//      node <仓>/scripts/gates.mjs` 会去 /tmp 找 .venv ⇒ 找不到 ⇒ 退回 PATH 上的
//      python ⇒ 那里没有 allin_governance ⇒ exit 3「找不到门禁套件」，
//      而真实原因只是「你在别的目录敲了这条命令」。判据把 cwd 当成仓根，是假红的来源。
//   2. **显式把被判的仓根交给门禁层**（`--root <仓根>`）。套件跑在已安装的包里，
//      每道门禁的 `--root` 默认要靠 .git 上溯，而它上溯的起点是**包的位置**，
//      不是本仓。不显式给，就会出现「判的是别的仓」或「一个 .git 都没找到」。
//
// 为什么 --root 放在 `--` 之后（转发给每道门禁）而不是 run.ts 自己的参数：
//   薄壳必须对**任何已安装的 2.x 包**都能用。2.3.0 的 run.ts 不认识自己的
//   `--root`（未知参数），而 20 道门禁的 CLI 契约里 `--root` 一直都在
//   （repocheck 的 rules_gate.py 就靠它）。转发形态两种版本都成立 ——
//   升级包不该让消费仓的 CI 先红一轮。
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

// 仓根：本文件在 <仓根>/scripts/ 下 ⇒ 上一级就是仓根。绝不用 cwd。
const REPO = resolve(import.meta.dirname, "..");

// 解释器优先级：显式 env → 本仓 .venv（装包的那个）→ PATH 里的 python。
// .venv 同样按 REPO 找，不按 cwd 找（见文件头第 1 条）。
const venvPy = join(REPO, ".venv",
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
      `  解释器：${PY}\n` +
      "  先 `pip install allin-governance`（公共核已独立成仓），或用 ALLIN_PYTHON 指定带该包的解释器。"
  );
  if (found.stderr) console.error(found.stderr.trim());
  process.exit(3);
}

// 调用方自己给了 --root 就不再注入（显式优先）；否则把本仓仓根交给门禁层。
// 已有 `--` 分隔符时插到转发段的最前面，避免出现第二个 `--`。
const args = process.argv.slice(2);
if (!args.includes("--root")) {
  const separator = args.indexOf("--");
  if (separator === -1) args.push("--", "--root", REPO);
  else args.splice(separator + 1, 0, "--root", REPO);
}

// run.ts 内部会自己找解释器（优先取 DSH_GOVERNANCE_PYTHON）；不指定的话它会用 PATH 上的
// python3 —— 那里可能装着**另一份** allin-governance（旧版 run.ts），导致路径推导错位。
const r = spawnSync("node", [runTs, ...args], {
  stdio: "inherit",
  env: { ...process.env, DSH_GOVERNANCE_PYTHON: PY },
});
process.exit(r.status === null ? 1 : r.status);
