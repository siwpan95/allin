/**
 * allin-console · preload（SPEC-205 §C3）
 *
 * 只暴露白名单方法，不暴露 ipcRenderer 本体、不暴露 require、不暴露 process。
 * 这是渲染层与主进程之间唯一的门。
 */
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('allin', {
  /** 项目清单（读 @allin/core 的 registry） */
  listProjects: () => ipcRenderer.invoke('projects:list'),

  /**
   * 调项目 CLI。
   * @param {string} projectId
   * @param {'info'|'version'|'selfcheck'|'launch'|'stop'|'logs'} subcommand
   * @param {string[]} extraArgs
   */
  runCli: (projectId, subcommand, extraArgs = []) =>
    ipcRenderer.invoke('cli:run', { projectId, subcommand, extraArgs }),

  /** 正在运行的项目 id 列表（来自 @allin/core 的 pid 表 + 存活探测） */
  runningIds: () => ipcRenderer.invoke('projects:running'),

  /** 启动项目（走 @allin/core.startEntry，pid 记在 core 那边） */
  start: (projectId) => ipcRenderer.invoke('project:start', projectId),

  /** 停止项目（走 @allin/core.stopEntry，含终止梯） */
  stop: (projectId) => ipcRenderer.invoke('project:stop', projectId),

  /** 任务日志尾部（读 @allin/core 的 tasks.log，只读） */
  logs: (projectId, lines = 60) => ipcRenderer.invoke('logs:tail', { projectId, lines }),
})
