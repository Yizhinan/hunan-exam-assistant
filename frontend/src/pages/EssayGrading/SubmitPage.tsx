import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { essayApi, type GradingResult } from "../../services/api";
import { Send, Loader2, Sparkles, FileText, HelpCircle } from "lucide-react";

export default function SubmitPage() {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [material, setMaterial] = useState("");
  const [answer, setAnswer] = useState("");
  const [useRag, setUseRag] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result: GradingResult = await essayApi.grade({
        question,
        material: material || undefined,
        answer,
        use_rag: useRag,
      });
      navigate(`/essay/${result.essay_id}`, { state: result });
    } catch (err) {
      setError(err instanceof Error ? err.message : "批改请求失败");
    } finally {
      setLoading(false);
    }
  };

  const answerLen = answer.replace(/\s/g, "").length;

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="page-heading flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-brand-500" />
          申论批改
        </h1>
        <p className="page-subtitle">提交题目和你的作答，AI 将从五个维度给出评分和修改建议</p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 rounded-2xl px-4 py-3 mb-6 text-sm border border-red-100">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Question */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            <HelpCircle className="h-4 w-4 text-brand-500" />
            <label className="text-sm font-semibold text-warm-900">申论题目</label>
          </div>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            required
            minLength={10}
            placeholder="请输入或粘贴申论题目..."
            className="input-field h-24 resize-none"
          />
        </div>

        {/* Material */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="h-4 w-4 text-amber-500" />
            <label className="text-sm font-semibold text-warm-900">
              给定资料（选填）
            </label>
            <span className="text-xs text-warm-400">申论材料是作答的根据，AI 会判断你是否紧扣材料</span>
          </div>
          <textarea
            value={material}
            onChange={(e) => setMaterial(e.target.value)}
            placeholder="在此粘贴申论给定资料（参考材料），可选填..."
            className="input-field h-40 resize-none text-sm leading-relaxed"
          />
        </div>

        {/* Answer */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-brand-500" />
              <label className="text-sm font-semibold text-warm-900">你的作答</label>
            </div>
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
              answerLen >= 600 ? "bg-green-50 text-green-600" :
              answerLen >= 300 ? "bg-amber-50 text-amber-600" :
              "bg-warm-100 text-warm-400"
            }`}>
              {answerLen} 字
            </span>
          </div>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            required
            minLength={50}
            placeholder="在此输入或粘贴你的申论作答..."
            className="input-field h-72 resize-none leading-relaxed"
          />
        </div>

        {/* Submit bar */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <label onClick={() => setUseRag(!useRag)} className="flex items-center gap-2.5 cursor-pointer select-none">
            <div className={`relative w-10 h-5 rounded-full transition-colors ${useRag ? "bg-brand-500" : "bg-warm-300"}`}>
              <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform ${useRag ? "left-5" : "left-0.5"}`} />
            </div>
            <span className="text-sm text-warm-600">RAG 增强批改</span>
          </label>

          <button type="submit" disabled={loading} className="btn-accent px-6 py-3">
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                AI 正在批改...
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                提交批改
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
