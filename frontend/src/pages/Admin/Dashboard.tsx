import { useState, useEffect } from "react";
import { knowledgeApi, type DocumentItem } from "../../services/api";
import { Database, Search, FileText, RefreshCw, HardDrive } from "lucide-react";

export default function Dashboard() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<{ content: string; score: number }[]>([]);

  const loadDocuments = () => {
    setLoading(true);
    knowledgeApi.getDocuments(1, 50).then((res) => {
      setDocuments(res.documents); setTotal(res.total);
    }).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { loadDocuments(); }, []);

  const handleSearch = async () => {
    if (!searchQ.trim()) return;
    try {
      const res = await knowledgeApi.search(searchQ, "exam", 5);
      setSearchResults(res.results);
    } catch (err) { console.error(err); }
  };

  const stats = [
    { icon: Database, label: "知识库文档", value: total, color: "text-emerald-600", bg: "bg-emerald-50" },
    { icon: FileText, label: "已入库分块", value: documents.reduce((s, d) => s + d.chunk_count, 0), color: "text-blue-600", bg: "bg-blue-50" },
    { icon: RefreshCw, label: "爬虫状态", value: "定时运行", color: "text-amber-600", bg: "bg-amber-50" },
    { icon: HardDrive, label: "存储引擎", value: "SQLite + ChromaDB", color: "text-violet-600", bg: "bg-violet-50" },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="page-heading">管理后台</h1>
        <p className="page-subtitle">知识库管理、检索测试、爬虫监控</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="card p-4">
            <div className={`w-9 h-9 rounded-xl ${s.bg} flex items-center justify-center mb-3`}>
              <s.icon className={`h-5 w-5 ${s.color}`} />
            </div>
            <div className="text-2xl font-bold text-warm-900">
              {typeof s.value === "number" ? s.value : s.value}
            </div>
            <div className="text-xs text-warm-400 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Search test */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-warm-900 mb-3 flex items-center gap-2">
          <Search className="h-4 w-4 text-brand-500" /> 知识库检索测试
        </h2>
        <div className="flex gap-2 mb-4">
          <input type="text" value={searchQ} onChange={(e) => setSearchQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="输入检索词..." className="input-field" />
          <button onClick={handleSearch} className="btn-primary">检索</button>
        </div>
        {searchResults.length > 0 && (
          <div className="space-y-2">
            {searchResults.map((r, i) => (
              <div key={i} className="bg-warm-50 rounded-xl p-3 text-sm">
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-warm-400">相似度: {(r.score * 100).toFixed(1)}%</span>
                </div>
                <p className="text-warm-600 line-clamp-4">{r.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Document list */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-warm-900 mb-4">文档列表</h2>
        {loading ? (
          <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-500" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-warm-100 text-left">
                  <th className="pb-2 font-medium text-warm-500">标题</th>
                  <th className="pb-2 font-medium text-warm-500">类型</th>
                  <th className="pb-2 font-medium text-warm-500">来源</th>
                  <th className="pb-2 font-medium text-warm-500">分块</th>
                  <th className="pb-2 font-medium text-warm-500">状态</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} className="border-b border-warm-50">
                    <td className="py-2.5 text-warm-900 max-w-xs truncate">{doc.title}</td>
                    <td className="py-2.5"><span className="tag tag-green">{doc.doc_type}</span></td>
                    <td className="py-2.5 text-warm-500">{doc.source_name || "-"}</td>
                    <td className="py-2.5 text-warm-500">{doc.chunk_count}</td>
                    <td className="py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        doc.status === "ingested" ? "bg-emerald-50 text-emerald-600"
                        : doc.status === "error" ? "bg-red-50 text-red-600"
                        : "bg-amber-50 text-amber-600"
                      }`}>{doc.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
