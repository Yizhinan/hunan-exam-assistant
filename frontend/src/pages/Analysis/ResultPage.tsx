import { useEffect, useState, useMemo } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, BarChart3, RefreshCw } from "lucide-react";
import { analysisApi, type AnalysisResult, type TrendDataPoint, type StatsOverview as StatsOverviewType } from "../../services/api";
import PositionCard from "../../components/analysis/PositionCard";
import StatsOverview from "../../components/analysis/StatsOverview";
import TrendChart from "../../components/analysis/TrendChart";

// Simple spinner while loading
function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
    </div>
  );
}

export default function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [result, setResult] = useState<AnalysisResult | null>(
    (location.state as AnalysisResult) || null
  );
  const [stats, setStats] = useState<StatsOverviewType | null>(null);
  const [trendData, setTrendData] = useState<TrendDataPoint[]>([]);
  const [loading, setLoading] = useState(false);

  // Always fetch fresh data from API on mount (location.state may be stale)
  useEffect(() => {
    if (searchParams.toString()) {
      setLoading(true);
      const params: Record<string, any> = {};
      const keys = ["birth_year","gender","education","degree","major","political_status","work_experience_years","preferred_cities","preferred_category","preferred_essay_category","year","exclude_professional_subject"];
      keys.forEach(k => {
        const v = searchParams.get(k);
        if (v) {
          // exclude_professional_subject 是布尔值，需要特殊处理
          if (k === "exclude_professional_subject") {
            params[k] = v === "true";
          } else {
            params[k] = k === "birth_year" || k === "work_experience_years" || k === "year" ? parseInt(v) : v;
          }
        }
      });
      analysisApi.recommend(params)
        .then(setResult)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [searchParams.toString()]);

  // Fetch stats on mount
  useEffect(() => {
    analysisApi.getStats().then(setStats).catch(() => {});
  }, []);

  // Fetch trend for first recommended city
  useEffect(() => {
    if (result?.recommendations?.length) {
      const city = result.recommendations[0].city;
      analysisApi.getTrend(city).then((res) => setTrendData(res.data)).catch(() => {});
    }
  }, [result]);

  // Tier distribution
  const tierCounts = useMemo(() => {
    const counts: Record<string, number> = { "保底": 0, "稳妥": 0, "冲刺": 0 };
    result?.recommendations.forEach(p => {
      counts[p.tier] = (counts[p.tier] || 0) + 1;
    });
    return counts;
  }, [result]);

  if (loading) return <Spinner />;
  if (!result) {
    return (
      <div className="text-center py-20 space-y-4">
        <RefreshCw className="h-10 w-10 text-warm-300 mx-auto" />
        <p className="text-warm-500">未找到分析结果</p>
        <button onClick={() => navigate("/analysis")} className="btn-primary">去填写信息</button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back */}
      <button onClick={() => navigate("/analysis")} className="btn-ghost text-sm">
        <ArrowLeft className="h-4 w-4" /> 返回修改
      </button>

      {/* Title */}
      <div>
        <h1 className="page-heading flex items-center gap-2">
          🎯 岗位推荐结果
        </h1>
        <p className="text-sm text-warm-500 mt-1">{result.summary}</p>
      </div>

      {/* Stats overview */}
      <StatsOverview
        stats={stats}
        matchedCount={result.matched_positions}
        totalCount={result.total_positions}
        tierCounts={tierCounts}
      />

      {/* Recommendations header */}
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-warm-900 flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-brand-500" />
          推荐岗位 ({result.recommendations.length})
          <span className="text-xs text-warm-400 font-normal">
            按综合难度从易到难排列
          </span>
        </h2>
      </div>

      {/* Position cards */}
      <div className="space-y-4">
        {result.recommendations.map((pos) => (
          <PositionCard key={pos.id} pos={pos} />
        ))}
      </div>

      {/* Trend chart */}
      {trendData.length > 0 && (
        <TrendChart data={trendData} />
      )}

      {/* Data source note */}
      <div className="card p-4 bg-warm-50/50 border-warm-200/50">
        <p className="text-xs text-warm-400 text-center">
          数据来源：湖南省人事考试网历年进面名单公示。分数为进面最低分/最高分/平均分，供参考。
          难度分综合进面分、竞争比、招录人数等多维度计算，数值越低越好考。
        </p>
      </div>
    </div>
  );
}
