import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  if (command === 'build') {
    let url
    try { url = new URL(process.env.VITE_API_BASE || env.VITE_API_BASE) } catch { /* validated below */ }
    if (!url || url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
      throw new Error('VITE_API_BASE must be an HTTPS backend origin for a production build.')
    }
  }
  return { plugins: [react(), tailwindcss()] }
})
