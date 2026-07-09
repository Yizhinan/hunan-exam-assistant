import { useState, useEffect, useCallback } from "react";
import { eventsApi, EventOut } from "../../services/api";
import { Calendar, Search, ChevronLeft, ChevronRight } from "lucide-react";

const CATEGORIES = ["全部", "科技", "政治党建", "经济", "文化", "体育", "外交", "民生", "生态"];
const RELEVANCE_OPTIONS = [
  { value: "", label: "全部" },
  { value: "必知", label: "必知" },
  { value: "了解", label: "了解" },
  { value: "拓展", label: "拓展" },
];

const CATEGORY_COLORS: Record<string, string> = {
  "科技": "bg-blue-100 text-blue-700",
  "政治党建": "bg-red-100 text-red-700",
  "经济": "bg-amber-100 text-amber-700",
  "文化": "bg-purple-100 text-purple-700",
  "体育": "bg-green-100 text-green-700",
  "外交": "bg-indigo-100 text-indigo-700",
  "民生": "bg-teal-100 text-teal-700",
  "生态": "bg-emerald-100 text-emerald-700",
};

const RELEVANCE_COLORS: Record<string, string> = {
  "必知": "bg-red-50 text-red-600 border-red-200",
  "了解": "bg-blue-50 text-blue-600 border-blue-200",
  "拓展": "bg-warm-100 text-warm-500 border-warm-200",
};

export default function EventsPage() {
  const [events, setEvents] = useState<EventOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("全部");
  const [relevance, setRelevance] = useState("");
  const pageSize = 12;

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
      };
      if (category !== "全部") params.category = category;
      if (relevance) params.relevance = relevance;

      const res = await eventsApi.list(params as any);
      setEvents(res.items);
      setTotal(res.total);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [page, category, relevance]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-warm-900">时政大事件</h1>
        <p className="text-sm text-warm-500 mt-1">
          年度重大时政事件整理，常识备考一站掌握
        </p>
      </div>

      {/* Filters */}
      <div className="card p-4 space-y-3">
        {/* Category tabs */}
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => { setCategory(cat); setPage(1); }}
              className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
                category === cat
                  ? "bg-brand-600 text-white"
                  : "bg-warm-50 text-warm-500 hover:bg-warm-100"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Relevance filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-warm-400">考试相关度：</span>
          {RELEVANCE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { setRelevance(opt.value); setPage(1); }}
              className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                relevance === opt.value
                  ? "bg-brand-600 text-white"
                  : "bg-warm-50 text-warm-500 hover:bg-warm-100"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Event grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card p-5 animate-pulse">
              <div className="h-3 bg-warm-100 rounded w-16 mb-3" />
              <div className="h-5 bg-warm-100 rounded w-full mb-2" />
              <div className="h-4 bg-warm-50 rounded w-full mb-1" />
              <div className="h-4 bg-warm-50 rounded w-2/3" />
            </div>
          ))}
        </div>
      ) : events.length === 0 ? (
        <div className="card p-12 text-center">
          <Search className="h-10 w-10 text-warm-300 mx-auto mb-3" />
          <p className="text-warm-500">暂无事件，请尝试调整筛选条件</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {events.map((e) => (
              <div
                key={e.id}
                className="card p-5 hover:shadow-elevated transition-all duration-200"
              >
                <div className="flex items-center gap-2 mb-2.5">
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                      CATEGORY_COLORS[e.category] || "bg-warm-100 text-warm-500"
                    }`}
                  >
                    {e.category}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full border ${
                      RELEVANCE_COLORS[e.relevance] || "bg-warm-50 text-warm-400 border-warm-200"
                    }`}
                  >
                    {e.relevance}
                  </span>
                </div>
                <h3 className="font-semibold text-warm-900 text-sm mb-2 leading-snug">
                  {e.title}
                </h3>
                <p className="text-xs text-warm-500 leading-relaxed mb-3">
                  {e.description}
                </p>
                <div className="flex items-center gap-3 text-xs text-warm-400">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {e.event_date}
                  </span>
                  {e.source && (
                    <span className="truncate">{e.source}</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-icon disabled:opacity-30"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm text-warm-500">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-icon disabled:opacity-30"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
