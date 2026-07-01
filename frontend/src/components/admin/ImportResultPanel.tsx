import { CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";
import type { ImportResult } from "../../services/api";

interface ImportResultPanelProps {
  result: ImportResult | null;
  loading: boolean;
}

export default function ImportResultPanel({ result, loading }: ImportResultPanelProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-warm-500 py-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        正在导入，请稍候...
      </div>
    );
  }

  if (!result) return null;

  const hasErrors = result.errors.length > 0;

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className={`rounded-2xl p-4 border ${hasErrors ? "bg-amber-50 border-amber-200" : "bg-emerald-50 border-emerald-200"}`}>
        <div className="flex items-center gap-2 mb-3">
          {hasErrors ? (
            <AlertTriangle className="h-5 w-5 text-amber-600" />
          ) : (
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          )}
          <span className={`font-semibold text-sm ${hasErrors ? "text-amber-800" : "text-emerald-800"}`}>
            {hasErrors ? "导入完成（部分异常）" : "导入完成"}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
          <Stat label="总行数" value={result.total_rows} />
          <Stat label="新增" value={result.created} color="text-emerald-600" />
          <Stat label="更新" value={result.updated} color="text-blue-600" />
          <Stat label="跳过" value={result.skipped} color="text-amber-600" />
          {result.not_found > 0 && (
            <Stat label="未匹配" value={result.not_found} color="text-red-600" />
          )}
        </div>
      </div>

      {/* Errors */}
      {hasErrors && (
        <details className="text-xs">
          <summary className="cursor-pointer text-warm-500 hover:text-warm-700 py-1 select-none">
            ⚠️ {result.errors.length} 条错误详情
          </summary>
          <div className="mt-2 max-h-48 overflow-y-auto space-y-1 bg-red-50 rounded-xl p-3 border border-red-100">
            {result.errors.slice(0, 20).map((err, i) => (
              <div key={i} className="text-red-700 leading-relaxed">
                {err.row && <span className="font-medium">第{err.row}行: </span>}
                {err.department && <span className="text-red-500">{err.department} / </span>}
                {err.position_name && <span className="text-red-500">{err.position_name}</span>}
                {err.message && <span> — {err.message}</span>}
              </div>
            ))}
            {result.errors.length > 20 && (
              <p className="text-warm-400 mt-1">...还有 {result.errors.length - 20} 条</p>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

function Stat({ label, value, color = "text-warm-700" }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-white/60 rounded-xl px-3 py-2 text-center">
      <div className={`text-lg font-bold ${color}`}>{value.toLocaleString()}</div>
      <div className="text-warm-400 mt-0.5">{label}</div>
    </div>
  );
}
