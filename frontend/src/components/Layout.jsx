import { Outlet, useLocation } from "react-router-dom"
import Nav from "./Nav"
import Footer from "./Footer"

export default function Layout() {
  const { pathname } = useLocation()
  return (
    <div className="min-h-screen">
      <Nav />
      <div className="max-w-5xl mx-auto px-6 pb-4 pt-12">
        <main key={pathname} className="page-enter">
          <Outlet />
        </main>
        <Footer />
      </div>
    </div>
  )
}
