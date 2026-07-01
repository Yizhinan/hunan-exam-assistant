import { useState, useEffect } from "react";
import { knowledgeApi, analysisApi, type DocumentItem, type ImportResult } from "../../services/api";
import { Database, Search, FileText, RefreshCw, HardDrive, Upload, Download, Brain } from "lucide-react";
import FileUploadZone from "../../components/admin/FileUploadZone";
import ImportResultPanel from "../../components/admin/ImportResultPanel";

type AdminTab = "knowledge" | "import";

export default function Dashboard() {
  const [tab, setTab] = useState<AdminTab>("knowledge");

  // --- Knowledge tab state ---
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

  // --- Import tab state ---
  const currentYear = new Date().getFullYear();
  const [importYear, setImportYear] = useState(currentYear);
  const [posFile, setPosFile] = useState<File | null>(null);
  const [scoreFile, setScoreFile] = useState<File | null>(null);
  const [posResult, setPosResult] = useState<ImportResult | null>(null);
  const [scoreResult, setScoreResult] = useState<ImportResult | null>(null);
  const [posLoading, setPosLoading] = useState(false);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [posError, setPosError] = useState("");
  const [scoreError, setScoreError] = useState("");
  const [cacheRefreshing, setCacheRefreshing] = useState(false);
  const [cacheMsg, setCacheMsg] = useState("");

  const handleImportPositions = async () => {
    if (!posFile) return;
    setPosLoading(true);
    setPosError("");
    setPosResult(null);
    try {
      const res = await analysisApi.importPositions(posFile, importYear);
      setPosResult(res);
    } catch (err: any) {
      setPosError(err.message || "导入失败");
    } finally {
      setPosLoading(false);
    }
  };

  const handleImportScores = async () => {
    if (!scoreFile) return;
    setScoreLoading(true);
    setScoreError("");
    setScoreResult(null);
    try {
      const res = await analysisApi.importScores(scoreFile, importYear);
      setScoreResult(res);
    } catch (err: any) {
      setScoreError(err.message || "导入失败");
    } finally {
      setScoreLoading(false);
    }
  };

  const handleRefreshCache = async () => {
    setCacheRefreshing(true);
    setCacheMsg("");
    try {
      const res = await fetch("/api/analysis/cache/refresh", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      const data = await res.json();
      setCacheMsg(`缓存已刷新，共 ${data.size || "?"} 个岗位完成评分`);
    } catch (err: any) {
      setCacheMsg(`刷新失败: ${err.message}`);
    } finally {
      setCacheRefreshing(false);
    }
  };

  // --- Stats ---
  const stats = [
    { icon: Database, label: "知识库文档", value: total, color: "text-emerald-600", bg: "bg-emerald-50" },
    { icon: FileText, label: "已入库分块", value: documents.reduce((s, d) => s + d.chunk_count, 0), color: "text-blue-600", bg: "bg-blue-50" },
    { icon: RefreshCw, label: "爬虫状态", value: "定时运行", color: "text-amber-600", bg: "bg-amber-50" },
    { icon: HardDrive, label: "存储引擎", value: "SQLite + ChromaDB", color: "text-violet-600", bg: "bg-violet-50" },
  ];

  const tabs: { key: AdminTab; label: string; icon: typeof Database }[] = [
    { key: "knowledge", label: "知识库", icon: Database },
    { key: "import", label: "数据导入", icon: Upload },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="page-heading">管理后台</h1>
        <p className="page-subtitle">知识库管理 · 岗位数据导入 · 缓存维护</p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
              tab === t.key
                ? "bg-brand-500 text-white shadow-sm"
                : "bg-white text-warm-600 border border-warm-200 hover:border-brand-200"
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* ======== Knowledge Tab ======== */}
      {tab === "knowledge" && (
        <>
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
        </>
      )}

      {/* ======== Import Tab ======== */}
      {tab === "import" && (
        <div className="space-y-6">
          {/* Year selector + cache refresh */}
          <div className="card p-4 flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-warm-700">
              <span className="font-medium">导入年份：</span>
              <select
                value={importYear}
                onChange={(e) => setImportYear(Number(e.target.value))}
                className="input-field w-28 py-2"
              >
                {Array.from({ length: 20 }, (_, i) => importYear - 10 + i).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
            <div className="border-l border-warm-200 pl-4 ml-auto">
              <button
                onClick={handleRefreshCache}
                disabled={cacheRefreshing}
                className="btn-secondary text-sm py-2 flex items-center gap-2 disabled:opacity-60"
              >
                <Brain className={`h-4 w-4 ${cacheRefreshing ? "animate-spin" : ""}`} />
                {cacheRefreshing ? "刷新中..." : "刷新难度评分缓存"}
              </button>
            </div>
            {cacheMsg && (
              <span className="text-xs text-brand-600 w-full">{cacheMsg}</span>
            )}
          </div>

          {/* Section 1: Import Positions */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-warm-900 mb-1 flex items-center gap-2">
              <Upload className="h-4 w-4 text-brand-500" />
              导入岗位 Excel
            </h2>
            <p className="text-xs text-warm-400 mb-4">
              支持多 sheet 页（省直机关、市州及以下、法院、检察院、公安、综合执法）。
              表头需包含：考区、单位名称、单位层级、职位名称、笔试考试科目、招录人数 等 23 列。
              去重：同一 (单位名称, 职位名称, 年份) 自动覆盖更新。
            </p>

            <FileUploadZone
              onFileSelect={setPosFile}
              disabled={posLoading}
              hint="拖拽岗位 Excel 到此处，或点击选择文件"
            />

            {posFile && (
              <button
                onClick={handleImportPositions}
                disabled={posLoading}
                className="btn-accent mt-4 text-sm py-2.5 px-6 flex items-center gap-2 disabled:opacity-60"
              >
                <Upload className="h-4 w-4" />
                {posLoading ? "正在导入岗位..." : `开始导入 ${posFile.name}`}
              </button>
            )}

            {posError && (
              <div className="mt-3 text-sm text-red-600 bg-red-50 rounded-xl px-4 py-2.5 border border-red-100">
                {posError}
              </div>
            )}

            <div className="mt-4">
              <ImportResultPanel result={posResult} loading={posLoading} />
            </div>
          </div>

          {/* Section 2: Import Scores */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-warm-900 mb-1 flex items-center gap-2">
              <Download className="h-4 w-4 text-amber-500" />
              导入进面成绩 Excel
            </h2>
            <p className="text-xs text-warm-400 mb-4">
              表头需包含：序号、姓名、准考证号、单位名称、职位名称、
              行政职业能力测验成绩、申论成绩、专业成绩、笔试综合成绩、笔试排名。
              按 (单位名称, 职位名称) 聚合进面最低/最高/平均分。
            </p>

            <FileUploadZone
              onFileSelect={setScoreFile}
              disabled={scoreLoading}
              hint="拖拽进面成绩 Excel 到此处，或点击选择文件"
            />

            {scoreFile && (
              <button
                onClick={handleImportScores}
                disabled={scoreLoading}
                className="btn-accent mt-4 text-sm py-2.5 px-6 flex items-center gap-2 disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                {scoreLoading ? "正在导入成绩..." : `开始导入 ${scoreFile.name}`}
              </button>
            )}

            {scoreError && (
              <div className="mt-3 text-sm text-red-600 bg-red-50 rounded-xl px-4 py-2.5 border border-red-100">
                {scoreError}
              </div>
            )}

            <div className="mt-4">
              <ImportResultPanel result={scoreResult} loading={scoreLoading} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
