const inputClass =
  "w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500";
const labelClass = "mb-1 block text-xs font-medium text-slate-400";

function normalizeAuth(nextType) {
  switch (nextType) {
    case "NO_AUTH":
      return { auth_type: "NO_AUTH" };
    case "BEARER":
      return { auth_type: "BEARER", token: "" };
    case "API_KEY":
      return { auth_type: "API_KEY", header_name: "", header_value: "" };
    case "BASIC":
      return { auth_type: "BASIC", username: "", password: "" };
    default:
      return { auth_type: "NO_AUTH" };
  }
}

export function AuthSection({ auth, onChange }) {
  const setType = (auth_type) => {
    onChange(normalizeAuth(auth_type));
  };

  const patch = (partial) => {
    onChange({ ...auth, ...partial });
  };

  return (
    <fieldset className="flex flex-col gap-4 rounded-xl border border-slate-700/80 bg-slate-900/40 p-4">
      <legend className="text-sm font-semibold text-slate-200">Аутентификация</legend>

      <div>
        <label className={labelClass} htmlFor="auth-type">
          Тип
        </label>
        <select
          id="auth-type"
          className={inputClass}
          value={auth.auth_type}
          onChange={(e) => setType(e.target.value)}
        >
          <option value="NO_AUTH">Без авторизации</option>
          <option value="BEARER">Bearer</option>
          <option value="API_KEY">API Key (заголовок)</option>
          <option value="BASIC">Basic</option>
        </select>
      </div>

      {auth.auth_type === "BEARER" && (
        <div>
          <label className={labelClass} htmlFor="auth-token">
            Token
          </label>
          <input
            id="auth-token"
            type="password"
            autoComplete="off"
            className={inputClass}
            placeholder="Bearer-токен"
            value={auth.token ?? ""}
            onChange={(e) => patch({ token: e.target.value })}
          />
        </div>
      )}

      {auth.auth_type === "API_KEY" && (
        <>
          <div>
            <label className={labelClass} htmlFor="auth-header-name">
              Имя заголовка
            </label>
            <input
              id="auth-header-name"
              className={inputClass}
              placeholder="X-Api-Key"
              value={auth.header_name ?? ""}
              onChange={(e) => patch({ header_name: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="auth-header-value">
              Значение
            </label>
            <input
              id="auth-header-value"
              type="password"
              autoComplete="off"
              className={inputClass}
              placeholder="Секрет"
              value={auth.header_value ?? ""}
              onChange={(e) => patch({ header_value: e.target.value })}
            />
          </div>
        </>
      )}

      {auth.auth_type === "BASIC" && (
        <>
          <div>
            <label className={labelClass} htmlFor="auth-basic-user">
              Имя пользователя
            </label>
            <input
              id="auth-basic-user"
              className={inputClass}
              autoComplete="username"
              value={auth.username ?? ""}
              onChange={(e) => patch({ username: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="auth-basic-pass">
              Пароль
            </label>
            <input
              id="auth-basic-pass"
              type="password"
              autoComplete="current-password"
              className={inputClass}
              value={auth.password ?? ""}
              onChange={(e) => patch({ password: e.target.value })}
            />
          </div>
        </>
      )}
    </fieldset>
  );
}
