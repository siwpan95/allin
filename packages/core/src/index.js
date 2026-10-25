// @allin/core —— 平台内核聚合导出。
export { loadRegistry, loadPorts, validateEntry, PORTS_YAML, KNOWN_GAMEPLAY } from './registry.js'
export { startEntry, stopEntry, isRunning, runningIds, runningInfo, shutdownAll, logTask, DATA_DIR, PLATFORM_ROOT } from './launch.js'
export { listWorkshop, subscribe, unsubscribe, checkUpdate, update, rollback, auditWorkshop } from './workshop.js'
export { fetchBranchCommit } from './gitee.js'
export { probeEntry, probePort, STARTING_GRACE_MS } from './probe.js'
