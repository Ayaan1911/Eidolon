import { useState } from "react"
import HomePage from "./pages/HomePage"
import ExposureReport from "./pages/ExposureReport"

export default function App() {
  const [result, setResult] = useState(null)

  return result ? (
    <ExposureReport result={result} onReset={() => setResult(null)} />
  ) : (
    <HomePage onResult={setResult} />
  )
}
