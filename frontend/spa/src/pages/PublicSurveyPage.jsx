import { useParams } from "react-router-dom";
import { SurveyTakeExperience } from "../components/questionnaires/SurveyTakeExperience.jsx";

/** Публичная страница прохождения опроса (Битрикс / MAX): без Layout, только форма. */
export function PublicSurveyPage() {
  const { id } = useParams();

  if (!id) {
    return (
      <div className="min-h-screen bg-slate-950 p-6 text-center text-sm text-red-400">
        Некорректная ссылка: не указан идентификатор опросника.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8">
      <SurveyTakeExperience questionnaireId={id} variant="public" />
    </div>
  );
}
