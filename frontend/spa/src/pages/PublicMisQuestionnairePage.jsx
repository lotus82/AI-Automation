import { useSearchParams } from "react-router-dom";
import { SurveyTakeExperience } from "../components/questionnaires/SurveyTakeExperience.jsx";
import { PAGE_H1, PAGE_TEXT } from "../styles/pageLayout.js";

/** Публичное прохождение опросника по ссылке из MAX (JWT в query `t`). */
export function PublicMisQuestionnairePage() {
  const [searchParams] = useSearchParams();
  const token = (searchParams.get("t") || "").trim();

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-teal-50/80 to-slate-50 px-4 py-10">
        <div className="mx-auto max-w-lg rounded-2xl border border-amber-200 bg-amber-50/90 p-6 text-sm text-amber-900 shadow-sm">
          <p className="font-medium">Ссылка неполная</p>
          <p className="mt-2 text-amber-800/90">
            Откройте ссылку из сообщения бота целиком — в адресе должен быть параметр с приглашением.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-teal-50/80 to-slate-50 px-4 py-8 sm:py-12">
      <SurveyTakeExperience inviteToken={token} variant="public" />
    </div>
  );
}
