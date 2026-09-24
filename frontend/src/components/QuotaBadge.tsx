import type { QuotaStatus } from "../lib/types";

type Props = {
  quota: QuotaStatus | null;
  onLogin: () => void;
  onLogout: () => void;
};

function formatNumber(value: number | null) {
  if (value === null) {
    return "不限";
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  }

  return String(value);
}

export function QuotaBadge({ quota, onLogin, onLogout }: Props) {
  const authenticated = quota?.authenticated ?? false;

  return (
    <div className="auth-area">
      {quota ? (
        <div className="quota-chip" title="当前账号额度">
          <span className="auth-dot" data-authenticated={authenticated} />
          <span>{authenticated ? "已登录" : "游客"}</span>
          <span>
            问题 {formatNumber(quota.remaining_questions)}
          </span>
          <span>
            Token {formatNumber(quota.remaining_tokens)}
          </span>
        </div>
      ) : null}

      {authenticated ? (
        <button className="text-button" type="button" onClick={onLogout}>
          退出
        </button>
      ) : (
        <button className="text-button" type="button" onClick={onLogin}>
          登录
        </button>
      )}
    </div>
  );
}
