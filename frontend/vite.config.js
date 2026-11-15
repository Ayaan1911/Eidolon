import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { defineConfig, loadEnv } from 'vite'

const deployConfig = JSON.parse(readFileSync(new URL('./vercel.json', import.meta.url), 'utf8'))
const policy = deployConfig.headers.flatMap((rule) => rule.headers)
  .find((header) => header.key === 'Content-Security-Policy').value
const connectSources = policy.split(';').find((directive) => directive.trim().startsWith('connect-src '))
  .trim().split(/\s+/).slice(1)

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  if (command === 'build') {
    let url
    try { url = new URL(process.env.VITE_API_BASE || env.VITE_API_BASE) } catch { /* validated below */ }
    if (!url || url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
      throw new Error('VITE_API_BASE must be an HTTPS backend origin for a production build.')
    }
    if (!connectSources.includes(url.origin)) {
      throw new Error('Add VITE_API_BASE to connect-src in frontend/vercel.json before building.')
    }
  }
  return { plugins: [react(), tailwindcss()] }
})
