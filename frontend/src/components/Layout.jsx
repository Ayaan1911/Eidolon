import { Outlet, useLocation } from "react-router-dom"
import Nav from "./Nav"
import Footer from "./Footer"

// Persistent shell: sticky nav, routed page (re-keyed per route so it plays
// the enter transition), then the site footer.
export default function Layout() {
  const { pathname } = useLocation()
  return (
    <div className="min-h-screen font-sans">
      <Nav />
      <div className="max-w-3xl mx-auto px-5 pb-4 pt-12">
        <main key={pathname} className="page-enter">
          <Outlet />
        </main>
        <Footer />
      </div>
    </div>
  )
}
