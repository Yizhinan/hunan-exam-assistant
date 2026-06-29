import { Shield, CheckCircle2, AlertTriangle } from "lucide-react";
import DifficultyRing from "./DifficultyRing";
import type { PositionOut } from "../../services/api";

const TIER_CONFIG: Record<string, { color: string; bg: string; label: string; icon: typeof Shield }> = {
  "保底": { color: "text-emerald-600", bg: "bg-emerald-50", label: "容易上岸", icon: CheckCircle2 },
  "稳妥": { color: "text-amber-600", bg: "bg-amber-50", label: "正常发挥", icon: AlertTriangle },
  "冲刺": { color: "text-red-600", bg: "bg-red-50", label: "需要冲刺", icon: AlertTriangle },
};

const CATEGORY_LABELS: Record<string, string> = {
  "省市直": "省市直岗", "行政执法": "行政执法岗", "县乡基层": "县乡基层岗", "综合通用": "综合",
};

export default function PositionCard({ pos }: { pos: PositionOut }) {
  const tierStyle = TIER_CONFIG[pos.tier] || TIER_CONFIG["稳妥"];
  const TierIcon = tierStyle.icon;

  return (
    <div className="card p-5 hover:shadow-elevated transition-shadow">
      {/* Header row: location + category + tier + difficulty ring */}
      <div className="flex items-start gap-4">
        <DifficultyRing score={pos.difficulty_score} tier={pos.tier as "保底" | "稳妥" | "冲刺"} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-xs font-medium bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full">
              {pos.city_label}
            </span>
            <span className="text-xs text-warm-400">
              {CATEGORY_LABELS[pos.exam_category] || pos.exam_category}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${tierStyle.bg} ${tierStyle.color}`}>
              <TierIcon className="h-3 w-3 inline mr-0.5" />{tierStyle.label}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              pos.risk_level === "低" ? "bg-emerald-50 text-emerald-600" :
              pos.risk_level === "中" ? "bg-amber-50 text-amber-600" :
              "bg-red-50 text-red-600"
            }`}>
              {pos.risk_level === "低" ? "竞争温和" : pos.risk_level === "中" ? "有一定竞争" : "竞争激烈"}
            </span>
          </div>
          <h3 className="font-semibold text-warm-900">{pos.department}</h3>
          <p className="text-sm text-warm-500">{pos.position_name}</p>
        </div>
        <div className="shrink-0 text-right">
          <div className={`text-xl font-bold ${
            pos.match_score >= 80 ? "text-emerald-600" :
            pos.match_score >= 60 ? "text-brand-600" : "text-amber-600"
          }`}>{pos.match_score}</div>
          <div className="text-[10px] text-warm-400">匹配度</div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3 mt-4">
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

      {/* Requirements tags */}
      <div className="flex flex-wrap gap-1.5 mt-3 text-[11px] text-warm-500">
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

      {/* Expandable: match details + difficulty breakdown */}
      <details className="mt-3 text-xs">
        <summary className="text-warm-400 cursor-pointer hover:text-warm-600">
          匹配详情 & 难度分项
        </summary>
        <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Match details */}
          <div className="space-y-0.5">
            <div className="text-[11px] font-medium text-warm-500 mb-1">匹配分析</div>
            {pos.match_details.map((d, i) => (
              <div key={i} className={d.startsWith("✅") ? "text-emerald-700" : d.startsWith("❌") ? "text-red-600" : "text-amber-600"}>
                {d}
              </div>
            ))}
          </div>
          {/* Difficulty breakdown */}
          {pos.difficulty_breakdown && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-medium text-warm-500 mb-1">难度分项（越低越容易）</div>
              <div className="flex justify-between text-warm-600">
                <span>进面分因子</span>
                <span className="font-medium">{pos.difficulty_breakdown.admission_score}</span>
              </div>
              <div className="flex justify-between text-warm-600">
                <span>竞争比因子</span>
                <span className="font-medium">{pos.difficulty_breakdown.competition_ratio}</span>
              </div>
              <div className="flex justify-between text-warm-600">
                <span>招录规模因子</span>
                <span className="font-medium">{pos.difficulty_breakdown.enrollment_scale}</span>
              </div>
              <div className="flex justify-between text-warm-600">
                <span>趋势修正</span>
                <span className="font-medium">{pos.difficulty_breakdown.trend_adjustment}</span>
              </div>
              <div className="flex justify-between text-warm-700 font-semibold border-t border-warm-100 pt-1 mt-1">
                <span>综合难度分</span>
                <span>{pos.difficulty_breakdown.total}</span>
              </div>
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
