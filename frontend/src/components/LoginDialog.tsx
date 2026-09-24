import { useState } from "react";
import type { FormEvent } from "react";
import { LoaderCircle, LockKeyhole, X } from "lucide-react";

type Props = {
  onClose: () => void;
  onLogin: (username: string, password: string) => Promise<void>;
};

export function LoginDialog({ onClose, onLogin }: Props) {
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("Demo@2026");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      await onLogin(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="login-dialog" role="dialog" aria-modal="true">
        <div className="login-header">
          <div>
            <p className="eyebrow">固定演示账号</p>
            <h2>登录</h2>
          </div>
          <button
            type="button"
            className="icon-button"
            title="关闭"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            账号
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </label>
          <label>
            密码
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <LockKeyhole size={18} />
            )}
            登录
          </button>
        </form>
      </section>
    </div>
  );
}
