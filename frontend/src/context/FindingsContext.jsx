import { createContext, useContext, useState } from "react"

// Shared dossier state. Lives above the router outlet so findings survive
// navigation between /email, /photo, /repo and /dossier — the provider stays
// mounted while individual route pages mount and unmount underneath it.
const FindingsContext = createContext(null)

let nextId = 0

export function FindingsProvider({ children }) {
  const [findings, setFindings] = useState([])

  function addFindings(newFindings) {
    setFindings((prev) => [
      ...prev,
      ...newFindings.map((f) => ({ ...f, id: nextId++ })),
    ])
  }

  return (
    <FindingsContext.Provider value={{ findings, addFindings }}>
      {children}
    </FindingsContext.Provider>
  )
}

export function useFindings() {
  const ctx = useContext(FindingsContext)
  if (!ctx) throw new Error("useFindings must be used within a FindingsProvider")
  return ctx
}
