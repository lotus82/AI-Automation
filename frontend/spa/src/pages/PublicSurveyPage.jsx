import { useParams } from "react-router-dom";
import { SurveyTakeExperience } from "../components/questionnaires/SurveyTakeExperience.jsx";
import { PAGE_H1, PAGE_TEXT } from "../styles/pageLayout.js";

/** Публичная страница прохождения опроса (Битрикс / MAX): без Layout, только форма. */
export function PublicSurveyPage() {
  const { id } = useParams();

  if (!id) {
    return (
      <div className="min-h-screen bg-[#f0f7f6] p-6 text-center text-sm text-red-700">
        Некорректная ссылка: не указан идентификатор опросника.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#e8f4f2] via-[#f4f9f8] to-[#eef6f4] px-4 py-10">
      <header className="mx-auto mb-6 max-w-2xl text-center">
        <p className="text-xs font-medium uppercase tracking-wide text-teal-700/80">Опрос</p>
        <p className="mt-1 text-sm text-slate-600">Заполните поля ниже — после отправки будет сформировано текстовое заключение.</p>
      </header>
      <SurveyTakeExperience questionnaireId={id} variant="public" />
    </div>
  );
}
