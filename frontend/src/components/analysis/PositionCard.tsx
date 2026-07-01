import DifficultyRing from "./DifficultyRing";
import type { PositionOut } from "../../services/api";

const TIER_CONFIG: Record<string, { color: string; bg: string; label: string; scoreColor: string }> = {
  "保底": { color: "text-emerald-600", bg: "bg-emerald-50", label: "容易上岸", scoreColor: "text-emerald-600" },
  "稳妥": { color: "text-amber-600", bg: "bg-amber-50", label: "正常发挥", scoreColor: "text-amber-600" },
  "冲刺": { color: "text-red-600", bg: "bg-red-50", label: "需要冲刺", scoreColor: "text-red-600" },
};

const ORG_LABELS: Record<string, string> = {
  "省直机关及直属单位": "省直机关",
  "市州及以下机关": "市州及以下",
  "法院系统": "法院系统",
  "检察院系统": "检察院系统",
  "公安系统": "公安系统",
  "综合行政执法队伍": "行政执法",
};

function detectEssayCategory(examSubject: string | null): string | null {
  if (!examSubject) return null;
  if (examSubject.includes("行政执法卷")) return "行政执法卷";
  if (examSubject.includes("省市卷")) return "省市卷";
  if (examSubject.includes("县乡卷")) return "县乡卷";
  return null;
}

export default function PositionCard({ pos }: { pos: PositionOut }) {
  const tierStyle = TIER_CONFIG[pos.tier] || TIER_CONFIG["稳妥"];

  return (
    <div className="card p-5 hover:shadow-elevated transition-shadow">
      {/* Header row: difficulty ring + info + difficulty score hero */}
      <div className="flex items-start gap-4">
        <DifficultyRing score={pos.difficulty_score} tier={pos.tier as "保底" | "稳妥" | "冲刺"} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-xs font-medium bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full">
              {pos.city_label}
            </span>
            <span className="text-xs font-medium text-warm-500">
              {pos.org_category ? (ORG_LABELS[pos.org_category] || pos.org_category) : (ORG_LABELS[pos.exam_category] || pos.exam_category)}
            </span>
            {detectEssayCategory(pos.exam_subject) && (
              <span className="text-xs text-accent-600 bg-accent-50 px-1.5 py-0.5 rounded">
                {detectEssayCategory(pos.exam_subject)}
              </span>
            )}
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${tierStyle.bg} ${tierStyle.color}`}>
              {pos.tier}·{tierStyle.label}
            </span>
          </div>
          <h3 className="font-semibold text-warm-900">{pos.department}</h3>
          <p className="text-sm text-warm-500">{pos.position_name}</p>
        </div>
        {/* Hero: difficulty score */}
        <div className="shrink-0 text-right">
          <div className={`text-2xl font-bold ${tierStyle.scoreColor}`}>
            {pos.difficulty_score}
          </div>
          <div className="text-[10px] text-warm-400">上岸难度分</div>
          <div className="text-[10px] text-warm-300">满分100·越低越好</div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3 mt-4">
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className={`text-sm font-bold ${pos.predicted_score ? "text-brand-600" : "text-warm-300"}`}>
            {pos.predicted_score ?? "暂无"}
          </div>
          <div className="text-[10px] text-warm-400">预测进面分</div>
        </div>
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className={`text-sm font-bold ${pos.min_score_interview ? "text-warm-700" : "text-warm-300"}`}>
            {pos.min_score_interview ?? "暂无"}
          </div>
          <div className="text-[10px] text-warm-400">{pos.year}年最低进面</div>
        </div>
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className={`text-sm font-bold ${pos.competition_ratio ? "text-warm-700" : "text-warm-300"}`}>
            {pos.competition_ratio ? `${pos.competition_ratio}:1` : "暂无"}
          </div>
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
        {pos.exam_subject && (
          <span className={`px-2 py-0.5 rounded ${
            (pos.exam_subject.includes("公安") || pos.exam_subject.includes("专业知识") || pos.exam_subject.includes("专业科目"))
              ? "bg-red-50 text-red-600"
              : "bg-blue-50 text-blue-600"
          }`}>{pos.exam_subject}</span>
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
            <div className="text-[11px] font-medium text-warm-500 mb-1">
              匹配分析
              <span className={`ml-2 px-1.5 py-0.5 rounded text-[10px] ${
                pos.match_score >= 80 ? "bg-emerald-100 text-emerald-700" :
                pos.match_score >= 60 ? "bg-brand-100 text-brand-700" : "bg-amber-100 text-amber-700"
              }`}>匹配度 {pos.match_score}</span>
            </div>
            {pos.match_details.map((d, i) => (
              <div key={i} className={d.startsWith("✅") ? "text-emerald-700" : d.startsWith("❌") ? "text-red-600" : "text-amber-600"}>
                {d}
              </div>
            ))}
          </div>
          {/* Difficulty breakdown */}
          {pos.difficulty_breakdown && Object.keys(pos.difficulty_breakdown).length > 0 && (
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
