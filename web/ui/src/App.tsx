import { Route, Routes } from "react-router-dom";
import { MetaProvider } from "./lib/MetaContext";
import { ChatProvider } from "./lib/ChatContext";
import Shell from "./components/Shell";
import CommandCenter from "./pages/CommandCenter";
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

export default function App() {
  return (
    <MetaProvider>
      <ChatProvider>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<CommandCenter />} />
            <Route path="/team/:code" element={<TeamHUD />} />
            <Route path="/leaders" element={<Leaders />} />
            <Route path="/players" element={<Players />} />
            <Route path="/schedule" element={<SchedulePage />} />
            <Route path="/news" element={<NewsPage />} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/betting" element={<Betting />} />
            <Route path="/coaches" element={<Coaches />} />
            <Route path="/coach/:name" element={<CoachPage />} />
            <Route path="/refs" element={<Referees />} />
          </Route>
        </Routes>
      </ChatProvider>
    </MetaProvider>
  );
}
