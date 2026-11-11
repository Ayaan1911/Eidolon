import assert from "node:assert/strict"
import test from "node:test"
import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { createServer } from "vite"

test("photo picker remains keyboard reachable with a visible focus state", async () => {
  const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "silent" })
  try {
    const { default: PhotoCheck } = await vite.ssrLoadModule("/src/components/PhotoCheck.jsx")
    const { FindingsProvider } = await vite.ssrLoadModule("/src/context/FindingsContext.jsx")
    const html = renderToStaticMarkup(React.createElement(FindingsProvider, null, React.createElement(PhotoCheck)))
    assert.match(html, /<input[^>]*type="file"[^>]*class="sr-only"/)
    assert.match(html, /focus-within:border-edge/)
  } finally {
    await vite.close()
  }
})
