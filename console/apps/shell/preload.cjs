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
})
