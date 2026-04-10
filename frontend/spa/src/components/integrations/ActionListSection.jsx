import { HTTP_METHODS } from "./types.js";
import { ParameterEditor } from "./ParameterEditor.jsx";

const inputClass =
  "w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500";
const labelClass = "mb-1 block text-xs font-medium text-slate-400";

const emptyAction = () => ({
  name: "",
  description: "",
  method: "GET",
  path: "/",
  parameters: [],
  is_llm_tool: true,
});

export function ActionListSection({ actions, onChange }) {
  const updateAt = (index, partial) => {
    onChange(actions.map((a, i) => (i === index ? { ...a, ...partial } : a)));
  };

  const setParameters = (index, parameters) => {
    onChange(actions.map((a, i) => (i === index ? { ...a, parameters } : a)));
  };

  const removeAt = (index) => {
    onChange(actions.filter((_, i) => i !== index));
  };

  const addAction = () => {
    onChange([...actions, emptyAction()]);
  };

  return (
    <fieldset className="flex flex-col gap-4">
      <legend className="text-sm font-semibold text-slate-200">Действия (actions)</legend>

      {actions.map((action, index) => (
        <div
          key={index}
          className="flex flex-col gap-3 rounded-xl border border-slate-700/80 bg-slate-900/40 p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Action #{index + 1}
            </span>
            <button
              type="button"
              className="rounded border border-red-900/40 px-2 py-1 text-xs text-red-300 hover:bg-red-950/30"
              onClick={() => removeAt(index)}
            >
              Remove
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-1">
              <label className={labelClass} htmlFor={`action-name-${index}`}>
                name <span className="text-slate-500">(a-z, A-Z, 0-9, _, -)</span>
              </label>
              <input
                id={`action-name-${index}`}
                className={inputClass}
                pattern="^[a-zA-Z0-9_-]+$"
                title="Только латиница, цифры, _ и -"
                placeholder="get_order"
                value={action.name}
                onChange={(e) => updateAt(index, { name: e.target.value })}
              />
            </div>
            <div className="sm:col-span-1">
              <label className={labelClass} htmlFor={`action-method-${index}`}>
                method
              </label>
              <select
                id={`action-method-${index}`}
                className={inputClass}
                value={action.method}
                onChange={(e) => updateAt(index, { method: e.target.value })}
              >
                {HTTP_METHODS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className={labelClass} htmlFor={`action-path-${index}`}>
                path
              </label>
              <input
                id={`action-path-${index}`}
                className={inputClass}
                placeholder="/v1/orders/{order_id}"
                value={action.path}
                onChange={(e) => updateAt(index, { path: e.target.value })}
              />
            </div>
            <div className="sm:col-span-2">
              <label className={labelClass} htmlFor={`action-desc-${index}`}>
                description
              </label>
              <textarea
                id={`action-desc-${index}`}
                className={`${inputClass} min-h-[80px] resize-y`}
                rows={3}
                value={action.description}
                onChange={(e) => updateAt(index, { description: e.target.value })}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  className="rounded border-slate-600 text-emerald-600 focus:ring-emerald-500"
                  checked={action.is_llm_tool}
                  onChange={(e) => updateAt(index, { is_llm_tool: e.target.checked })}
                />
                is_llm_tool
              </label>
            </div>
          </div>

          <ParameterEditor
            parameters={action.parameters}
            onChange={(parameters) => setParameters(index, parameters)}
          />
        </div>
      ))}

      <button
        type="button"
        className="self-start rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700"
        onClick={addAction}
      >
        Add new action
      </button>
    </fieldset>
  );
}
