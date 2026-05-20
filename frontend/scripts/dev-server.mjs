/**
 * Vite dev server launcher with enlarged HTTP header limit.
 *
 * Node defaults to 8KB (CVE-2018-12121). Local dev often accumulates cookies on
 * localhost and triggers Vite 431 on HMR — see vite.dev troubleshooting.
 */
import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const viteBin = path.resolve(__dirname, '../node_modules/vite/bin/vite.js')
const nodeArgs = ['--max-http-header-size=32768', viteBin, ...process.argv.slice(2)]

const child = spawn(process.execPath, nodeArgs, {
  stdio: 'inherit',
  env: process.env,
  shell: process.platform === 'win32',
})

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }
  process.exit(code ?? 0)
})
