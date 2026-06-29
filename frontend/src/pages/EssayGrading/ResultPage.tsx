import { useEffect, useState } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
} from "recharts";
import {
  ArrowLeft, CheckCircle2, AlertCircle, Lightbulb, PenLine,
  Award, Target, Sparkles,
} from "lucide-react";
import { essayApi, type GradingResult } from "../../services/api";

const GRADE_MAP: Record<string, { label: string; color: string; bg: string }> = {
  "一类文": { label: "一类文", color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200" },
  "二类文": { label: "二类文", color: "text-blue-700", bg: "bg-blue-50 border-blue-200" },
  "三类文": { label: "三类文", color: "text-amber-700", bg: "bg-amber-50 border-amber-200" },
  "四类文": { label: "四类文", color: "text-red-700", bg: "bg-red-50 border-red-200" },
};

export default function ResultPage() {
  const { essayId } = useParams<{ essayId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [result, setResult] = useState<GradingResult | null>(
    (location.state as GradingResult) || null
  );
  const [loading, setLoading] = useState(!result);

  useEffect(() => {
    if (!result && essayId) {
      essayApi.getResult(essayId).then(setResult).catch(console.error).finally(() => setLoading(false));
    }
  }, [essayId, result]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
      </div>
    );
  }
  if (!result) {
    return (
      <div className="text-center py-20">
        <p className="text-warm-500">未找到批改结果</p>
        <button onClick={() => navigate("/essay")} className="btn-primary mt-4">返回批改</button>
      </div>
    );
  }

  const chartData = result.dimensions.map((d) => ({ dimension: d.name, score: d.score, fullMark: 10 }));
  const gradeStyle = GRADE_MAP[result.grade] || GRADE_MAP["三类文"];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back */}
      <button onClick={() => navigate("/essay")} className="btn-ghost text-sm">
        <ArrowLeft className="h-4 w-4" /> 返回批改
      </button>

      {/* Score hero */}
      <div className="card p-6 md:p-8">
        <div className="flex flex-col md:flex-row items-center gap-6 md:gap-10">
          {/* Score circle */}
          <div className="relative shrink-0">
            <svg className="w-32 h-32 transform -rotate-90">
              <circle cx="64" cy="64" r="56" fill="none" stroke="#e5e7eb" strokeWidth="8" />
              <circle
                cx="64" cy="64" r="56"
                fill="none"
                stroke="url(#scoreGradient)"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${(result.total_score / 100) * 352} 352`}
              />
              <defs>
                <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#1e6b4e" />
                  <stop offset="100%" stopColor="#40a976" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold text-brand-600">{result.total_score}</span>
              <span className="text-xs text-warm-400">/ 100</span>
            </div>
          </div>

          <div className="text-center md:text-left">
            <div className="flex items-center gap-2 justify-center md:justify-start mb-2">
              <Award className="h-5 w-5 text-brand-500" />
              <span className={`text-sm font-medium px-3 py-1 rounded-full border ${gradeStyle.bg} ${gradeStyle.color}`}>
                {result.grade}
              </span>
            </div>
            <p className="text-warm-500 text-sm max-w-sm">{result.overall_comment}</p>
            {result.hunan_relevance && (
              <div className="mt-3 inline-flex items-center gap-1.5 tag-green text-xs">
                <Target className="h-3 w-3" />
                {result.hunan_relevance}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Radar chart */}
      <div className="card p-5">
        <h3 className="text-sm font-semibold text-warm-900 mb-4 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-brand-500" />
          各维度评分
        </h3>
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={chartData}>
            <PolarGrid stroke="#e8e5df" />
            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12, fill: "#655c52" }} />
            <PolarRadiusAxis angle={90} domain={[0, 10]} tick={{ fontSize: 10, fill: "#b8b0a5" }} />
            <Radar name="得分" dataKey="score" stroke="#1e6b4e" fill="#1e6b4e" fillOpacity={0.15} strokeWidth={2} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Dimension cards */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-warm-900 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-brand-500" />
          逐维度评语
        </h3>
        {result.dimensions.map((dim) => (
          <div key={dim.key} className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <div>
                <span className="font-semibold text-warm-900">{dim.name}</span>
                <span className="text-xs text-warm-400 ml-2">权重 {Math.round(dim.weight * 100)}%</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-2xl font-bold text-brand-600">{dim.score}</span>
                <span className="text-xs text-warm-400">/ 10</span>
              </div>
            </div>
            <p className="text-sm text-warm-600 mb-3">{dim.comment}</p>
            {dim.highlights.length > 0 && (
              <div className="space-y-1 mb-2">
                {dim.highlights.map((h, i) => (
                  <div key={i} className="flex items-start gap-1.5 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" /><span>{h}</span></div>
                ))}
              </div>
            )}
            {dim.issues.length > 0 && (
              <div className="space-y-1">
                {dim.issues.map((issue, i) => (
                  <div key={i} className="flex items-start gap-1.5 text-sm text-red-600"><AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /><span>{issue}</span></div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Suggestions + Model revision */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-warm-900 mb-3 flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-amber-500" /> 修改建议
          </h3>
          <ul className="space-y-2">
            {result.suggestions.map((s, i) => (
              <li key={i} className="text-sm text-warm-700 bg-amber-50/50 rounded-xl px-3 py-2">{i + 1}. {s}</li>
            ))}
          </ul>
        </div>
        {result.model_revision && (
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-warm-900 mb-3 flex items-center gap-2">
              <PenLine className="h-4 w-4 text-brand-500" /> 范文参考
            </h3>
            <p className="text-sm text-warm-600 leading-relaxed italic border-l-3 border-brand-200 pl-4">
              {result.model_revision}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
