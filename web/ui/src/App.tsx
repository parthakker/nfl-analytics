import { Navigate, Route, Routes } from "react-router-dom";
import { MetaProvider } from "./lib/MetaContext";
import { ChatProvider } from "./lib/ChatContext";
import Shell from "./components/Shell";
import CommandCenter from "./pages/CommandCenter";
import Teams from "./pages/Teams";
import TeamHUD from "./pages/TeamHUD";
import Leaders from "./pages/Leaders";
import Players from "./pages/Players";
import SchedulePage from "./pages/SchedulePage";
import NewsPage from "./pages/NewsPage";
import Markets from "./pages/Markets";
import Betting from "./pages/Betting";
import Coaches from "./pages/Coaches";
import CoachPage from "./pages/CoachPage";
import Referees from "./pages/Referees";
import Matchup from "./pages/Matchup";
import PlayerPage from "./pages/PlayerPage";
import H2HExplorer from "./pages/H2HExplorer";
import Knowledge from "./pages/Knowledge";
import Ops from "./pages/Ops";
import ModelLab from "./pages/ModelLab";

/* Hubs are plural, details singular. Old paths redirect rather than 404 —
 * they are in Parth's history, in the knowledge markdown, and in shared links.
 * /matchup/:gameId deliberately stays put: five specs and several knowledge
 * chapters deep-link to it. */
export default function App() {
  return (
    <MetaProvider>
      <ChatProvider>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<CommandCenter />} />

            <Route path="/scores" element={<SchedulePage />} />
            <Route path="/schedule" element={<Navigate to="/scores" replace />} />

            <Route path="/teams" element={<Teams />} />
            <Route path="/team/:code" element={<TeamHUD />} />

            <Route path="/players" element={<Players />} />
            <Route path="/player/:gsis" element={<PlayerPage />} />
            <Route path="/leaders" element={<Leaders />} />

            <Route path="/betting" element={<Betting />} />
            <Route path="/markets" element={<Markets />} />

            <Route path="/knowledge" element={<Knowledge />} />
            <Route path="/knowledge/:slug" element={<Knowledge />} />

            <Route path="/coaches" element={<Coaches />} />
            <Route path="/coach/:name" element={<CoachPage />} />
            <Route path="/refs" element={<Referees />} />
            <Route path="/news" element={<NewsPage />} />
            <Route path="/h2h" element={<H2HExplorer />} />
            <Route path="/h2h/:a/:b" element={<H2HExplorer />} />
            <Route path="/matchup/:gameId" element={<Matchup />} />

            <Route path="/ops" element={<Ops />} />
            <Route path="/model" element={<ModelLab />} />
            <Route path="/model-lab" element={<Navigate to="/model" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ChatProvider>
    </MetaProvider>
  );
}
