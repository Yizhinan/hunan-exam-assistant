import { useLocation, useNavigate } from "react-router-dom";
import {
  Target, Shield, ArrowLeft,
  AlertTriangle, CheckCircle2, BarChart3,
} from "lucide-react";
import { type AnalysisResult, type PositionOut } from "../../services/api";

const RISK_CONFIG: Record<string, { color: string; bg: string; label: string; icon: typeof Shield }> = {
  "低": { color: "text-emerald-600", bg: "bg-emerald-50", label: "低风险", icon: CheckCircle2 },
  "中": { color: "text-amber-600", bg: "bg-amber-50", label: "中等风险", icon: AlertTriangle },
  "高": { color: "text-red-600", bg: "bg-red-50", label: "高风险", icon: AlertTriangle },
};

const CATEGORY_LABELS: Record<string, string> = {
  "省市直": "省市直岗", "行政执法": "行政执法岗", "县乡基层": "县乡基层岗", "综合通用": "综合",
};

function PositionCard({ pos }: { pos: PositionOut }) {
  const risk = RISK_CONFIG[pos.risk_level] || RISK_CONFIG["中"];

  return (
    <div className="card p-5 hover:shadow-elevated transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full">
              {pos.city_label}
            </span>
            <span className="text-xs text-warm-400">
              {CATEGORY_LABELS[pos.exam_category] || pos.exam_category}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${risk.bg} ${risk.color}`}>
              <risk.icon className="h-3 w-3 inline mr-0.5" />{risk.label}
            </span>
          </div>
          <h3 className="font-semibold text-warm-900">{pos.department}</h3>
          <p className="text-sm text-warm-500">{pos.position_name}</p>
        </div>
        <div className="shrink-0 ml-3 text-center">
          <div className={`text-2xl font-bold ${
            pos.match_score >= 80 ? "text-emerald-600" :
            pos.match_score >= 60 ? "text-brand-600" : "text-amber-600"
          }`}>{pos.match_score}</div>
          <div className="text-[10px] text-warm-400">匹配度</div>
        </div>
      </div>

      {/* Score info */}
      <div className="grid grid-cols-4 gap-3 mb-3">
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className="text-sm font-bold text-brand-600">{pos.predicted_score ?? "-"}</div>
          <div className="text-[10px] text-warm-400">预测进面分</div>
        </div>
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className="text-sm font-bold text-warm-700">{pos.avg_score_interview ?? "-"}</div>
          <div className="text-[10px] text-warm-400">{pos.year}年均分</div>
        </div>
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className="text-sm font-bold text-warm-700">{pos.competition_ratio ?? "-"}:1</div>
          <div className="text-[10px] text-warm-400">竞争比</div>
        </div>
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className="text-sm font-bold text-warm-700">{pos.enrollment_count}</div>
          <div className="text-[10px] text-warm-400">招录人数</div>
        </div>
      </div>

      {/* Requirements */}
      <div className="flex flex-wrap gap-1.5 text-[11px] text-warm-500">
        <span className="bg-warm-100 px-2 py-0.5 rounded">{pos.education_requirement}</span>
        <span className="bg-warm-100 px-2 py-0.5 rounded">{pos.degree_requirement}</span>
        <span className="bg-warm-100 px-2 py-0.5 rounded">
          {pos.major_requirement || "专业不限"}
        </span>
        <span className="bg-warm-100 px-2 py-0.5 rounded">{pos.political_requirement}</span>
        {pos.gender_requirement !== "不限" && (
          <span className="bg-warm-100 px-2 py-0.5 rounded">{pos.gender_requirement}</span>
        )}
      </div>

      {/* Match details (expandable) */}
      <details className="mt-3 text-xs">
        <summary className="text-warm-400 cursor-pointer hover:text-warm-600">匹配详情</summary>
        <div className="mt-2 space-y-0.5">
          {pos.match_details.map((d, i) => (
            <div key={i} className={d.startsWith("✅") ? "text-emerald-700" : d.startsWith("❌") ? "text-red-600" : "text-amber-600"}>
              {d}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

export default function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const result = location.state as AnalysisResult | null;

  if (!result) {
    return (
      <div className="text-center py-20">
        <p className="text-warm-500">未找到分析结果</p>
        <button onClick={() => navigate("/analysis")} className="btn-primary mt-4">去填写信息</button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <button onClick={() => navigate("/analysis")} className="btn-ghost text-sm">
        <ArrowLeft className="h-4 w-4" /> 返回修改
      </button>

      <div>
        <h1 className="page-heading flex items-center gap-2">
          <Target className="h-6 w-6 text-accent-500" />
          岗位推荐结果
        </h1>
      </div>

      {/* Summary card */}
      <div className="card p-6 bg-gradient-to-br from-brand-50 to-emerald-50 border-brand-100/50">
        <p className="text-sm text-warm-700 leading-relaxed">{result.summary}</p>
        <div className="flex items-center gap-4 mt-4 text-xs text-warm-500">
          <span className="flex items-center gap-1"><Target className="h-3.5 w-3.5 text-brand-500" />
            共 {result.total_positions} 个岗位，匹配 {result.matched_positions} 个
          </span>
        </div>
      </div>

      {/* Recommendations */}
      <div>
        <h2 className="font-semibold text-warm-900 mb-4 flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-brand-500" />
          推荐岗位 ({result.recommendations.length})
        </h2>
        <div className="space-y-4">
          {result.recommendations.map((pos) => (
            <PositionCard key={pos.id} pos={pos} />
          ))}
        </div>
      </div>

      {/* Note about data source */}
      <div className="card p-4 bg-warm-50/50 border-warm-200/50">
        <p className="text-xs text-warm-400 text-center">
          数据来源：湖南省人事考试网历年进面名单公示。分数为进面最低分/最高分/平均分，供参考。
        </p>
      </div>
    </div>
  );
}
