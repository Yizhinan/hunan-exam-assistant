import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { Sparkles, ArrowRight, Check } from "lucide-react";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const pwdStrength =
    password.length >= 8 ? "strong"
    : password.length >= 6 ? "medium"
    : password.length > 0 ? "weak"
    : "";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({ username, email, password, display_name: displayName });
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left: Hero — same as login */}
      <div className="hidden lg:flex lg:w-[480px] relative overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-brand-800">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-10 w-72 h-72 rounded-full bg-white/20 blur-3xl" />
          <div className="absolute bottom-40 right-10 w-96 h-96 rounded-full bg-brand-400/30 blur-3xl" />
        </div>
        <div className="relative flex flex-col justify-between p-12 text-white w-full">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
              <Sparkles className="h-5 w-5" />
            </div>
            <span className="font-semibold text-lg">湖南公考助手</span>
          </div>

          <div className="space-y-6">
            <h2 className="text-3xl font-bold leading-snug tracking-tight">
              加入备考社区
              <br />
              让 AI 助你一臂之力
            </h2>
            <div className="space-y-3">
              {[
                "AI 智能申论批改，五维度精准评分",
                "每日精选高分范文，积少成多",
                "专为湖南省考量身定制",
              ].map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-brand-100">
                  <Check className="h-4 w-4 text-brand-300 shrink-0" />
                  <span className="text-sm">{f}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="h-px w-16 bg-white/20 mb-4" />
            <p className="text-brand-200 text-sm">注册即表示同意服务条款和隐私政策</p>
          </div>
        </div>
      </div>

      {/* Right: Form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-warm-50">
        <div className="w-full max-w-[380px]">
          <div className="lg:hidden text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 mb-3">
              <Sparkles className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-warm-900">湖南公考助手</h1>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-warm-900">创建账号</h2>
            <p className="text-warm-500 mt-1.5">开始你的智能备考之旅</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-50 text-red-600 text-sm rounded-xl px-4 py-3 border border-red-100">
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-warm-700 mb-1.5">
                  用户名 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  minLength={2}
                  className="input-field"
                  placeholder="2-50个字符"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-warm-700 mb-1.5">
                  昵称
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="input-field"
                  placeholder="如何称呼你"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-warm-700 mb-1.5">
                邮箱 <span className="text-red-400">*</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input-field"
                placeholder="your@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-warm-700 mb-1.5">
                密码 <span className="text-red-400">*</span>
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="input-field"
                placeholder="至少6个字符"
              />
              {pwdStrength && (
                <div className="flex items-center gap-2 mt-2">
                  <div className="flex-1 h-1 rounded-full bg-warm-200">
                    <div
                      className={`h-full rounded-full transition-all ${
                        pwdStrength === "strong"
                          ? "w-full bg-green-500"
                          : pwdStrength === "medium"
                          ? "w-2/3 bg-amber-500"
                          : "w-1/3 bg-red-400"
                      }`}
                    />
                  </div>
                  <span className="text-[11px] text-warm-400">
                    {pwdStrength === "strong" ? "强" : pwdStrength === "medium" ? "中" : "弱"}
                  </span>
                </div>
              )}
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full py-3">
              {loading ? "注册中..." : "创建账号"}
              {!loading && <ArrowRight className="h-4 w-4" />}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-warm-500">
            已有账号？
            <Link to="/login" className="text-brand-600 hover:text-brand-700 font-medium ml-1">
              立即登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
