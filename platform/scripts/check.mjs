// check.mjs —— 无 GUI 配置审计（对齐 crawl_hub --check）：exit 0 = 全部通过。
import path from "node:path"
import { fileURLToPath } from "node:url"
import { loadRegistry } from "@allin/core"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REGISTRY = process.env.PLATFORM_REGISTRY || path.join(__dirname, "..", "registry", "projects")

const { entries, problems } = loadRegistry(REGISTRY)
if (problems.length) {
  console.error("[check] 注册表问题:")
  for (const p of problems) console.error("  - " + p)
  process.exit(1)
}
console.log("[check] 通过：" + entries.length + " 个项目清单全部有效")
for (const e of entries) {
  console.log("  - " + e.id + " (" + e.category + ")" + (e.port ? " 端口 " + e.port : "") + (e.manual ? " [manual]" : ""))
}
process.exit(0)
