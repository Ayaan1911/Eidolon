import { Routes, Route } from "react-router-dom"
import { FindingsProvider } from "./context/FindingsContext"
import Layout from "./components/Layout"
import ToolPage from "./components/ToolPage"
import Home from "./pages/Home"
import EmailCheck from "./components/EmailCheck"
import PhotoCheck from "./components/PhotoCheck"
import RepoScan from "./components/RepoScan"
import Dossier from "./components/Dossier"
import TrapLab from "./components/TrapLab"

// Per-route intro copy — the Mirror/Dossier voice, one or two sentences each.
const intro = {
  email:
    "Your address is the first thread an investigator pulls. Enter it and Eidolon checks it against known breach corpora — every dump it turns up becomes a line in your dossier.",
  photo:
    "A photo is rarely just an image. Drop one here and Eidolon reads the metadata a casual viewer never sees — the device that took it, the moment it was captured, sometimes the exact coordinates.",
  repo:
    "Public code carries private mistakes. Give Eidolon a GitHub handle and it scans that account's non-fork repositories for credentials committed and forgotten — keys and tokens still sitting in plain sight.",
  dossier:
    "Everything Eidolon finds collects here — one running case file that grows as you run each check. What a stranger could assemble about you, assembled in one place.",
  trapLab:
    "The other side of the mirror. Spin up a standalone canary — a link that quietly logs whoever opens it — without tying it to a finding. Deploy one, leave it where a snoop would look, and watch who bites.",
}

export default function App() {
  return (
    <FindingsProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route
            path="email"
            element={
              <ToolPage title="Email breach check" intro={intro.email}>
                <EmailCheck />
              </ToolPage>
            }
          />
          <Route
            path="photo"
            element={
              <ToolPage title="Photo metadata check" intro={intro.photo}>
                <PhotoCheck />
              </ToolPage>
            }
          />
          <Route
            path="repo"
            element={
              <ToolPage title="GitHub secret scan" intro={intro.repo}>
                <RepoScan />
              </ToolPage>
            }
          />
          <Route
            path="dossier"
            element={
              <ToolPage title="Dossier" intro={intro.dossier}>
                <Dossier />
              </ToolPage>
            }
          />
          <Route
            path="trap-lab"
            element={
              <ToolPage title="Trap Lab" intro={intro.trapLab}>
                <TrapLab />
              </ToolPage>
            }
          />
        </Route>
      </Routes>
    </FindingsProvider>
  )
}
