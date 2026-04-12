import { useState } from "react";
import { ActionListSection } from "./ActionListSection.jsx";
import { AuthSection } from "./AuthSection.jsx";

const inputClass =
  "w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500";
const labelClass = "mb-1 block text-xs font-medium text-slate-400";

const defaultState = () => ({
  name: "",
  base_url: "",
  auth: { auth_type: "NO_AUTH" },
  actions: [],
});

export function IntegrationForm({ onSubmit, initialData }) {
  const [data, setData] = useState(() => ({
    ...defaultState(),
    ...initialData,
    auth: initialData?.auth ?? { auth_type: "NO_AUTH" },
    actions: initialData?.actions ?? [],
  }));

  const setAuth = (auth) => {
    setData((d) => ({ ...d, auth }));
  };

  const setActions = (actions) => {
    setData((d) => ({ ...d, actions }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(data);
  };

  return (
    <form
      className="flex w-full min-w-0 flex-col gap-6 rounded-2xl border border-slate-700/80 bg-slate-900/50 p-6 shadow-lg backdrop-blur-sm"
      onSubmit={handleSubmit}
    >
      <h2 className="text-lg font-semibold text-white">Конфигурация интеграции</h2>

      <div className="flex flex-col gap-4">
        <div>
          <label className={labelClass} htmlFor="int-form-name">
            name
          </label>
          <input
            id="int-form-name"
            className={inputClass}
            value={data.name}
            onChange={(e) => setData((d) => ({ ...d, name: e.target.value }))}
            placeholder="Моя интеграция"
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="int-form-base-url">
            base_url
          </label>
          <input
            id="int-form-base-url"
            type="url"
            className={inputClass}
            value={data.base_url}
            onChange={(e) => setData((d) => ({ ...d, base_url: e.target.value }))}
            placeholder="https://api.example.com"
          />
        </div>
      </div>

      <AuthSection auth={data.auth} onChange={setAuth} />

      <ActionListSection actions={data.actions} onChange={setActions} />

      <button
        type="submit"
        className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500"
      >
        Save Integration
      </button>
    </form>
  );
}
