import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Calendar, Tag, ArrowRight, Search, Filter } from "lucide-react";
import { dailyApi, type DailyEssayListItem, type TopicItem, type CategoryInfo } from "../../services/api";

const CATEGORY_COLORS: Record<string, string> = {
  "行政执法": "bg-orange-50 text-orange-700 border-orange-200",
  "县乡基层": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "省市直": "bg-blue-50 text-blue-700 border-blue-200",
  "综合通用": "bg-violet-50 text-violet-700 border-violet-200",
};

const CATEGORY_LABELS: Record<string, string> = {
  "行政执法": "行政执法岗",
  "县乡基层": "县乡基层岗",
  "省市直": "省市直岗",
  "综合通用": "综合",
};

export default function ArchivePage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<DailyEssayListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [topics, setTopics] = useState<TopicItem[]>([]);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [selectedTopic, setSelectedTopic] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dailyApi.getTopics().then(setTopics).catch(() => {});
    dailyApi.getCategories().then(setCategories).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    dailyApi.getArchive(page, 12, selectedTopic || undefined, selectedCategory || undefined)
      .then((res) => { setItems(res.items); setTotal(res.total); })
      .catch(console.error).finally(() => setLoading(false));
  }, [page, selectedTopic, selectedCategory]);

  const totalPages = Math.ceil(total / 12);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="page-heading">范文归档</h1>
        <p className="page-subtitle">共 {total} 篇，支持按岗位类别和主题筛选</p>
      </div>

      {/* Filters */}
      <div className="card p-5 space-y-4">
        {/* Category filter */}
        {categories.length > 0 && (
          <div>
            <p className="text-xs font-medium text-warm-400 mb-2 flex items-center gap-1.5">
              <Filter className="h-3 w-3" /> 岗位类别
            </p>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => { setSelectedCategory(""); setPage(1); }}
                className={`text-xs px-3 py-1.5 rounded-lg transition-all ${
                  !selectedCategory ? "bg-brand-500 text-white" : "bg-warm-100 text-warm-600 hover:bg-warm-200"
                }`}>全部</button>
              {categories.map((c) => (
                <button key={c.category} onClick={() => { setSelectedCategory(c.category); setPage(1); }}
                  className={`text-xs px-3 py-1.5 rounded-lg transition-all ${
                    selectedCategory === c.category ? "bg-brand-500 text-white" : "bg-warm-100 text-warm-600 hover:bg-warm-200"
                  }`}>{c.label} ({c.count})</button>
              ))}
            </div>
          </div>
        )}

        {/* Topic filter */}
        {topics.length > 0 && (
          <div>
            <p className="text-xs font-medium text-warm-400 mb-2 flex items-center gap-1.5">
              <Tag className="h-3 w-3" /> 主题
            </p>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => { setSelectedTopic(""); setPage(1); }}
                className={`text-xs px-3 py-1.5 rounded-lg transition-all ${
                  !selectedTopic ? "bg-accent-500 text-white" : "bg-warm-100 text-warm-600 hover:bg-warm-200"
                }`}>全部</button>
              {topics.slice(0, 15).map((t) => (
                <button key={t.topic} onClick={() => { setSelectedTopic(t.topic); setPage(1); }}
                  className={`text-xs px-3 py-1.5 rounded-lg transition-all ${
                    selectedTopic === t.topic ? "bg-accent-500 text-white" : "bg-warm-100 text-warm-600 hover:bg-warm-200"
                  }`}>{t.topic} ({t.count})</button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-20">
          <Search className="h-10 w-10 mx-auto mb-4 text-warm-300" />
          <p className="text-warm-500">暂无范文</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <button key={item.id} onClick={() => navigate(`/daily/${item.id}`)}
              className="w-full card p-5 text-left hover:shadow-elevated transition-all group">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${CATEGORY_COLORS[item.exam_category] || CATEGORY_COLORS["综合通用"]}`}>
                      {CATEGORY_LABELS[item.exam_category] || item.exam_category}
                    </span>
                    {item.topic && <span className="text-xs text-warm-400 flex items-center gap-0.5"><Tag className="h-3 w-3" />{item.topic}</span>}
                  </div>
                  <h3 className="font-semibold text-warm-900 group-hover:text-brand-600 transition-colors line-clamp-2">
                    {item.title}
                  </h3>
                  {item.highlights && (
                    <p className="text-sm text-warm-500 line-clamp-1 mt-1">{item.highlights.replace(/[#*]/g, "").slice(0, 150)}</p>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-xs text-warm-400">
                    <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{item.recommend_date}</span>
                    {item.source_name && <span>{item.source_name}</span>}
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 text-warm-300 group-hover:text-brand-500 shrink-0 mt-2 transition-colors" />
              </div>
            </button>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary text-sm py-1.5">上一页</button>
          <span className="text-sm text-warm-500">{page} / {totalPages}</span>
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary text-sm py-1.5">下一页</button>
        </div>
      )}
    </div>
  );
}
