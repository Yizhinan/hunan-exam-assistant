import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { Sparkles, ArrowRight, Eye, EyeOff } from "lucide-react";

const quotes = [
  "公考之路，每一步都算数",
  "今天的努力，是明天的底气",
  "坚持就是胜利，付出终有回报",
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const quote = quotes[Math.floor(Math.random() * quotes.length)];

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left: Hero panel */}
      <div className="hidden lg:flex lg:w-[480px] relative overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-brand-800">
        {/* Decorative pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-10 w-72 h-72 rounded-full bg-white/20 blur-3xl" />
          <div className="absolute bottom-40 right-10 w-96 h-96 rounded-full bg-brand-400/30 blur-3xl" />
        </div>

        <div className="relative flex flex-col justify-between p-12 text-white w-full">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
              <Sparkles className="h-5 w-5" />
            </div>
            <span className="font-semibold text-lg">湖南公考助手</span>
          </div>

          {/* Quote */}
          <div className="space-y-6">
            <h2 className="text-3xl font-bold leading-snug tracking-tight">
              高效备考
              <br />
              从这里开始
            </h2>
            <p className="text-brand-100 text-base leading-relaxed max-w-sm">
              AI 驱动的申论批改，五维度精准评分。每日精选范文，助你积累申论素材。专为湖南考情优化。
            </p>
            <div className="flex items-center gap-3 pt-4">
              <div className="flex -space-x-2">
                {["湖", "南", "公"].map((c, i) => (
                  <div
                    key={i}
                    className="w-8 h-8 rounded-full bg-white/20 backdrop-blur border-2 border-brand-600 flex items-center justify-center text-xs font-bold"
                  >
                    {c}
                  </div>
                ))}
              </div>
              <span className="text-sm text-brand-200">已有 1,200+ 考生在使用</span>
            </div>
          </div>

          {/* Bottom quote */}
          <div>
            <div className="h-px w-16 bg-white/20 mb-4" />
            <p className="text-brand-200 italic text-sm">"{quote}"</p>
          </div>
        </div>
      </div>

      {/* Right: Login form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-warm-50">
        <div className="w-full max-w-[380px]">
          {/* Mobile logo */}
          <div className="lg:hidden text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 mb-3">
              <Sparkles className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-warm-900">湖南公考助手</h1>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-warm-900">欢迎回来</h2>
            <p className="text-warm-500 mt-1.5">登录你的账号继续学习</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-50 text-red-600 text-sm rounded-xl px-4 py-3 border border-red-100">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-warm-700 mb-1.5">
                用户名
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="input-field"
                placeholder="请输入用户名"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-warm-700 mb-1.5">
                密码
              </label>
              <div className="relative">
                <input
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="input-field pr-10"
                  placeholder="请输入密码"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-warm-400 hover:text-warm-600"
                >
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full py-3">
              {loading ? "登录中..." : "登录"}
              {!loading && <ArrowRight className="h-4 w-4" />}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-warm-500">
            还没有账号？
            <Link to="/register" className="text-brand-600 hover:text-brand-700 font-medium ml-1">
              立即注册
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
