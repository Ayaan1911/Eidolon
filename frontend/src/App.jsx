import { useState } from "react"
import HomePage from "./pages/HomePage"
import ExposureReport from "./pages/ExposureReport"
import PhotoCheck from "./pages/PhotoCheck"

export default function App() {
  const [view, setView] = useState("home")
  const [emailResult, setEmailResult] = useState(null)

  if (view === "photo") {
    return <PhotoCheck onBack={() => setView("home")} />
  }

  if (emailResult) {
    return (
      <ExposureReport
        result={emailResult}
        onReset={() => {
          setEmailResult(null)
          setView("home")
        }}
      />
    )
  }

  return (
    <HomePage onResult={setEmailResult} onCheckPhoto={() => setView("photo")} />
  )
}
