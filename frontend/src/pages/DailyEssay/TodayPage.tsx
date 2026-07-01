import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ExternalLink, Eye, BookOpen, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";
import { dailyApi, type DailyEssayOut, type TodayResponse, type RefreshResponse } from "../../services/api";

const CATEGORY_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  "行政执法": { label: "行政执法岗", color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-200" },
  "县乡基层": { label: "县乡基层岗", color: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200" },
  "省市直":  { label: "省市直岗", color: "text-blue-700", bg: "bg-blue-50", border: "border-blue-200" },
  "综合通用": { label: "综合通用", color: "text-violet-700", bg: "bg-violet-50", border: "border-violet-200" },
};

function EssayCard({ essay }: { essay: DailyEssayOut }) {
  const cfg = CATEGORY_CONFIG[essay.exam_category] || CATEGORY_CONFIG["综合通用"];

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-5 pb-2">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${cfg.bg} ${cfg.color} ${cfg.border}`}>
            {cfg.label}
          </span>
          {essay.topic && <span className="tag tag-green">{essay.topic}</span>}
          <span className="text-xs text-warm-400 flex items-center gap-1 ml-auto">
            <Eye className="h-3 w-3" /> {essay.view_count}
          </span>
        </div>
        <h2 className="text-lg font-bold text-warm-900 leading-snug">{essay.title}</h2>
        {essay.source_name && (
          <p className="text-xs text-warm-400 mt-1">来源：{essay.source_name}</p>
        )}
      </div>

      {/* Content */}
      <div className="px-5 py-3 max-h-64 overflow-y-auto">
        <article className="text-sm text-warm-700 leading-relaxed space-y-2 border-l-2 border-brand-100 pl-4">
          {essay.content.split("\n").map((para, i) =>
            para.trim() ? <p key={i} className="text-justify">{para}</p> : null
          )}
        </article>
      </div>

      {/* Highlights */}
      {essay.highlights && (
        <div className="mx-5 mb-3 bg-amber-50/50 rounded-2xl p-4 border border-amber-100/50">
          <h4 className="text-xs font-semibold text-amber-800 mb-2">📝 亮点分析</h4>
          <div className="text-xs text-amber-900 leading-relaxed space-y-1"
            dangerouslySetInnerHTML={{
              __html: essay.highlights.replace(/### (.+)/g, '<span class="font-semibold block mt-1.5">$1</span>'),
            }}
          />
        </div>
      )}

      {/* Key points */}
      {essay.key_points && (
        <div className="mx-5 mb-4 bg-brand-50/50 rounded-2xl p-4 border border-brand-100/50">
          <h4 className="text-xs font-semibold text-brand-800 mb-2">🎯 要点提炼</h4>
          <div className="text-xs text-brand-900 leading-relaxed space-y-1"
            dangerouslySetInnerHTML={{
              __html: essay.key_points.replace(/### (.+)/g, '<span class="font-semibold block mt-1.5">$1</span>'),
            }}
          />
        </div>
      )}

      {essay.source_url && (
        <div className="px-5 pb-4">
          <a href={essay.source_url} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-warm-400 hover:text-brand-600 transition-colors">
            <ExternalLink className="h-3 w-3" /> 查看原文
          </a>
        </div>
      )}
    </div>
  );
}

export default function TodayPage() {
  const { essayId } = useParams<{ essayId: string }>();
  const [data, setData] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setToast(null);
    try {
      const res: RefreshResponse = await dailyApi.refresh(true);
      setToast({ type: "success", message: res.message });
      // Auto-reload after a delay to let background scraping finish
      setTimeout(() => {
        dailyApi.getToday(activeCategory || undefined).then(setData).catch(() => {});
        setRefreshing(false);
      }, 15000);
    } catch (err: any) {
      setToast({ type: "error", message: `刷新失败：${err.message || "网络错误"}` });
      setRefreshing(false);
    }
  };

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 8000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    if (essayId) {
      dailyApi.getDetail(essayId).then((essay) => setData({
        date: essay.recommend_date, essays: [essay], categories_available: [essay.exam_category],
      })).catch((err) => setError(err.message)).finally(() => setLoading(false));
    } else {
      dailyApi.getToday(activeCategory || undefined).then((res) => {
        setData(res);
        if (!activeCategory && res.categories_available.length > 0) {
          setActiveCategory(res.categories_available[0]);
        }
      }).catch((err) => setError(err.message)).finally(() => setLoading(false));
    }
  }, [activeCategory, essayId]);

  if (loading) {
    return <div className="flex items-center justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" /></div>;
  }

  if (error || !data || data.essays.length === 0) {
    return (
      <div className="max-w-4xl mx-auto text-center py-20">
        <BookOpen className="h-12 w-12 mx-auto mb-4 text-warm-300" />
        <p className="text-warm-500">{error || "暂无范文"}</p>
        <p className="text-sm text-warm-400 mt-2 mb-4">点击下方按钮从人民网、求是网获取最新申论范文</p>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "正在获取范文…" : "🔄 手动刷新获取范文"}
        </button>
        {toast && (
          <div className={`mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm ${
            toast.type === "success"
              ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
              : "bg-red-50 text-red-800 border border-red-200"
          }`}>
            {toast.type === "success" ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            {toast.message}
          </div>
        )}
      </div>
    );
  }

  const essays = data.essays;
  const filteredEssays = activeCategory ? essays.filter((e) => e.exam_category === activeCategory) : essays;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Toast */}
      {toast && (
        <div className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm ${
          toast.type === "success"
            ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
            : "bg-red-50 text-red-800 border border-red-200"
        }`}>
          {toast.type === "success"
            ? <CheckCircle2 className="h-4 w-4 shrink-0" />
            : <AlertCircle className="h-4 w-4 shrink-0" />
          }
          <span className="flex-1">{toast.message}</span>
          <button onClick={() => setToast(null)} className="text-warm-400 hover:text-warm-600">✕</button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-heading">每日范文</h1>
          <p className="page-subtitle">{data.date} · 按岗位类型分类，每日更新</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="btn-secondary text-sm py-2 flex items-center gap-2 disabled:opacity-60"
            title="从人民网、求是网等公开网站获取最新范文"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "刷新中…" : "手动刷新"}
          </button>
          <Link to="/daily/archive" className="btn-secondary text-sm py-2">
            历史归档 →
          </Link>
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {Object.entries(CATEGORY_CONFIG).map(([key, cfg]) => {
          const hasEssays = essays.some((e) => e.exam_category === key);
          const isActive = activeCategory === key;
          return (
            <button key={key} onClick={() => setActiveCategory(key)} disabled={!hasEssays}
              className={`shrink-0 text-sm px-4 py-2.5 rounded-xl font-medium transition-all ${
                isActive
                  ? "bg-brand-500 text-white shadow-sm"
                  : hasEssays
                  ? "bg-white text-warm-700 border border-warm-200 hover:border-brand-200"
                  : "bg-warm-100 text-warm-300 cursor-not-allowed"
              }`}>
              {cfg.label}
              {hasEssays && <span className={`ml-1.5 text-xs ${isActive ? "text-brand-100" : "text-warm-400"}`}>
                {essays.filter((e) => e.exam_category === key).length}篇
              </span>}
            </button>
          );
        })}
      </div>

      {/* Essay cards */}
      <div className="space-y-6">
        {filteredEssays.map((essay) => <EssayCard key={essay.id} essay={essay} />)}
      </div>

      {filteredEssays.length === 0 && (
        <div className="text-center py-16 text-warm-400 text-sm">该类别暂无今日范文</div>
      )}
    </div>
  );
}
