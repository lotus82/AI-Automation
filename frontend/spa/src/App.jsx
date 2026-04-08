import { Navigate, Route, Routes } from "react-router-dom";
import { useBitrixAuth } from "./hooks/useBitrixAuth.js";
import { Layout } from "./layouts/Layout.jsx";
import { AITrainerPage } from "./pages/AITrainerPage.jsx";
import { BotsPage } from "./pages/BotsPage.jsx";
import { DashboardPage } from "./pages/DashboardPage.jsx";
import { KnowledgePage } from "./pages/KnowledgePage.jsx";
import { LeadgenPage } from "./pages/LeadgenPage.jsx";
import { PublicSurveyPage } from "./pages/PublicSurveyPage.jsx";
import { QuestionnairesPage } from "./pages/QuestionnairesPage.jsx";
import { QAPage } from "./pages/QAPage.jsx";
import { SchedulePage } from "./pages/SchedulePage.jsx";
import { ScenariosPage } from "./pages/ScenariosPage.jsx";
import { SettingsPage } from "./pages/SettingsPage.jsx";
import { TelephonyPage } from "./pages/TelephonyPage.jsx";
import { TesterPage } from "./pages/TesterPage.jsx";

export default function App() {
  useBitrixAuth();

  return (
    <Routes>
      <Route path="/public/survey/:id" element={<PublicSurveyPage />} />
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="qa-analytics" element={<QAPage />} />
        <Route path="ai-trainer" element={<AITrainerPage />} />
        <Route path="leadgen" element={<LeadgenPage />} />
        <Route path="tester" element={<TesterPage />} />
        <Route path="scenarios" element={<ScenariosPage />} />
        <Route path="telephony" element={<TelephonyPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="bots" element={<BotsPage />} />
        <Route path="schedule" element={<SchedulePage />} />
        <Route path="questionnaires" element={<QuestionnairesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
