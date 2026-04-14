import { Route, Routes } from "react-router-dom";
import { BitrixScenariosRedirect } from "./components/BitrixScenariosRedirect.jsx";
import { NavigateUnknown } from "./components/NavigateUnknown.jsx";
import { RedirectWithSearch } from "./components/RedirectWithSearch.jsx";
import { RequireAuth } from "./components/RequireAuth.jsx";
import { useBitrixAuth } from "./hooks/useBitrixAuth.js";
import { Layout } from "./layouts/Layout.jsx";
import { ScenariosIndexRedirect, ScenariosLayout } from "./layouts/ScenariosLayout.jsx";
import { AITrainerPage } from "./pages/AITrainerPage.jsx";
import { BotsPage } from "./pages/BotsPage.jsx";
import { FormsPage } from "./pages/FormsPage.jsx";
import { IntegrationsPage } from "./pages/IntegrationsPage.jsx";
import { KnowledgePage } from "./pages/KnowledgePage.jsx";
import { LandingPage } from "./pages/LandingPage.jsx";
import { LoginPage } from "./pages/LoginPage.jsx";
import { LogsPage } from "./pages/LogsPage.jsx";
import { LeadgenPage } from "./pages/LeadgenPage.jsx";
import { OrganizationsPage } from "./pages/OrganizationsPage.jsx";
import { OrgUsersPage } from "./pages/OrgUsersPage.jsx";
import { PublicRegistrationPage } from "./pages/PublicRegistrationPage.jsx";
import { PublicSurveyPage } from "./pages/PublicSurveyPage.jsx";
import { QuestionnairesPage } from "./pages/QuestionnairesPage.jsx";
import { QAPage } from "./pages/QAPage.jsx";
import { SchedulePage } from "./pages/SchedulePage.jsx";
import { RolesPage } from "./pages/RolesPage.jsx";
import { PublicShopPage } from "./pages/PublicShopPage.jsx";
import { SettingsPage } from "./pages/SettingsPage.jsx";
import { ShopsPage } from "./pages/ShopsPage.jsx";
import { TesterPage } from "./pages/TesterPage.jsx";

export default function App() {
  useBitrixAuth();

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      {/** Встраивание в Битрикс24: см. docs/BITRIX24_SCENARIOS_SETUP.md */}
      <Route path="/bitrix" element={<BitrixScenariosRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/public/survey/:id" element={<PublicSurveyPage />} />
      <Route path="/public/register/:eventId" element={<PublicRegistrationPage />} />
      <Route path="/public/shop/:slug" element={<PublicShopPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="scenarios" element={<ScenariosLayout />}>
            <Route index element={<ScenariosIndexRedirect />} />
            <Route path="qa-analytics" element={<QAPage />} />
            <Route path="ai-trainer" element={<AITrainerPage />} />
            <Route path="leadgen" element={<LeadgenPage />} />
          </Route>
          <Route
            path="qa-analytics"
            element={<RedirectWithSearch to="/scenarios/qa-analytics" />}
          />
          <Route
            path="ai-trainer"
            element={<RedirectWithSearch to="/scenarios/ai-trainer" />}
          />
          <Route path="leadgen" element={<RedirectWithSearch to="/scenarios/leadgen" />} />
          <Route path="telephony" element={<RedirectWithSearch to="/scenarios/leadgen" />} />
          <Route path="tester" element={<TesterPage />} />
          <Route path="integrations" element={<IntegrationsPage />} />
          <Route path="roles" element={<RolesPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="logs" element={<LogsPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="bots" element={<BotsPage />} />
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="questionnaires" element={<QuestionnairesPage />} />
          <Route path="forms" element={<FormsPage />} />
          <Route path="shops" element={<ShopsPage />} />
          <Route path="portal/organizations" element={<OrganizationsPage />} />
          <Route path="portal/users" element={<OrgUsersPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NavigateUnknown />} />
    </Routes>
  );
}
