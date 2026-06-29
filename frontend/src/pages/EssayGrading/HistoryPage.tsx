import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { TrendingUp, Clock, FileText, ChevronRight, ArrowRight } from "lucide-react";
import { essayApi, type EssayHistoryItem } from "../../services/api";

export default function HistoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<EssayHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    essayApi.getHistory(page).then((res) => { setItems(res.items); setTotal(res.total); })
      .catch(console.error).finally(() => setLoading(false));
  }, [page]);

  const trendData = [...items].reverse().map((item) => ({
    date: new Date(item.created_at).toLocaleDateString("zh-CN", { month: "short", day: "numeric" }),
    score: item.total_score,
  }));

  const pageSize = 10;
  const totalPages = Math.ceil(total / pageSize);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="page-heading flex items-center gap-2">
          <Clock className="h-6 w-6 text-brand-500" />
          批改历史
        </h1>
        <p className="page-subtitle">共 {total} 篇批改记录</p>
      </div>

      {items.length === 0 ? (
        <div className="card p-12 text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 text-warm-300" />
          <p className="text-warm-500 mb-4">还没有批改记录</p>
          <button onClick={() => navigate("/essay")} className="btn-primary">
            开始第一篇批改 <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <>
          {/* Trend — only if 2+ scored items */}
          {trendData.filter((d) => d.score != null).length >= 2 && (
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-warm-900 mb-4 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-brand-500" /> 得分趋势
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0ebe3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#b8b0a5" }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#b8b0a5" }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#1e6b4e" strokeWidth={2.5}
                    dot={{ r: 3, fill: "#1e6b4e" }} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* List */}
          <div className="space-y-3">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => navigate(`/essay/${item.id}`)}
                disabled={item.status !== "completed"}
                className="w-full card p-4 text-left hover:shadow-elevated transition-all group disabled:opacity-50"
              >
                <div className="flex items-center gap-4">
                  {/* Score badge */}
                  <div className={`shrink-0 w-14 h-14 rounded-2xl flex flex-col items-center justify-center ${
                    item.total_score != null
                      ? "bg-brand-50 text-brand-700"
                      : "bg-warm-100 text-warm-400"
                  }`}>
                    <span className="text-lg font-bold leading-none">
                      {item.total_score ?? "-"}
                    </span>
                    {item.grade && <span className="text-[10px] mt-0.5">{item.grade}</span>}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-warm-900 truncate">{item.question}</p>
                    <div className="flex items-center gap-3 mt-1.5">
                      <span className="text-xs text-warm-400 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(item.created_at).toLocaleDateString("zh-CN")}
                      </span>
                      {item.status === "grading" && (
                        <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">批改中</span>
                      )}
                      {item.status === "error" && (
                        <span className="text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-full">失败</span>
                      )}
                    </div>
                  </div>

                  <ChevronRight className="h-5 w-5 text-warm-300 group-hover:text-brand-500 transition-colors shrink-0" />
                </div>
              </button>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="btn-secondary text-sm py-1.5">上一页</button>
              <span className="text-sm text-warm-500">{page} / {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="btn-secondary text-sm py-1.5">下一页</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
