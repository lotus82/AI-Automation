import { PARAMETER_ROW_TYPES } from "./types.js";

const inputClass =
  "w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-xs text-white placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";

export function ParameterEditor({ parameters, onChange }) {
  const updateAt = (index, partial) => {
    const next = parameters.map((p, i) => (i === index ? { ...p, ...partial } : p));
    onChange(next);
  };

  const removeAt = (index) => {
    onChange(parameters.filter((_, i) => i !== index));
  };

  const addParameter = () => {
    onChange([...parameters, { name: "", type: "string", description: "", required: true }]);
  };

  return (
    <div className="mt-3 flex flex-col gap-2 rounded-lg border border-slate-700/60 bg-slate-950/50 p-3">
      <div className="text-xs font-medium text-slate-400">Параметры</div>
      {parameters.length === 0 ? (
        <p className="text-xs text-slate-500">Нет параметров.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {parameters.map((param, index) => (
            <div
              key={index}
              className="grid grid-cols-1 gap-2 border-b border-slate-800 pb-2 last:border-0 sm:grid-cols-12 sm:items-end"
            >
              <div className="sm:col-span-2">
                <label className="mb-0.5 block text-[10px] uppercase text-slate-500">Имя</label>
                <input
                  className={inputClass}
                  placeholder="param"
                  value={param.name}
                  onChange={(e) => updateAt(index, { name: e.target.value })}
                  aria-label={`Имя параметра ${index + 1}`}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-0.5 block text-[10px] uppercase text-slate-500">Тип</label>
                <select
                  className={inputClass}
                  value={param.type}
                  onChange={(e) => updateAt(index, { type: e.target.value })}
                  aria-label={`Тип параметра ${index + 1}`}
                >
                  {PARAMETER_ROW_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-5">
                <label className="mb-0.5 block text-[10px] uppercase text-slate-500">Описание</label>
                <input
                  className={inputClass}
                  placeholder="Описание для LLM"
                  value={param.description}
                  onChange={(e) => updateAt(index, { description: e.target.value })}
                />
              </div>
              <div className="flex items-center gap-2 sm:col-span-2">
                <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    className="rounded border-slate-600 text-emerald-600 focus:ring-emerald-500"
                    checked={param.required}
                    onChange={(e) => updateAt(index, { required: e.target.checked })}
                  />
                  Обязательный
                </label>
              </div>
              <div className="flex sm:col-span-1 sm:justify-end">
                <button
                  type="button"
                  className="rounded border border-red-900/40 px-2 py-1 text-xs text-red-300 hover:bg-red-950/30"
                  onClick={() => removeAt(index)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        className="self-start rounded border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800"
        onClick={addParameter}
      >
        Add Parameter
      </button>
    </div>
  );
}
