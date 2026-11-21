/**
 * allin-console · 入口（SPEC-205 §C3）
 *
 * 只负责应用生命周期；窗口与 IPC 逻辑在 app.js（供 smoke.mjs 复用）。
 */
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { app } = require('electron')
import { createConsoleWindow, registerIpc } from './app.js'

app.whenReady().then(() => {
  registerIpc()
  createConsoleWindow()
  app.on('activate', () => {
    createConsoleWindow()
  })
})

app.on('window-all-closed', () => {
  app.quit()
})
