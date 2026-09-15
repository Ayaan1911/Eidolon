import { Outlet } from "react-router-dom"
import Nav from "./Nav"

// Persistent shell: sticky nav on top, routed page in the outlet below.
export default function Layout() {
  return (
    <div className="min-h-screen font-sans">
      <Nav />
      <div className="max-w-2xl mx-auto px-4 pb-20 pt-12">
        <Outlet />
      </div>
    </div>
  )
}
