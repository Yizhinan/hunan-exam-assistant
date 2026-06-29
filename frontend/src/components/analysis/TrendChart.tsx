import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { TrendDataPoint } from "../../services/api";

interface Props {
  data: TrendDataPoint[];
  className?: string;
}

export default function TrendChart({ data, className = "" }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className={`card p-5 ${className}`}>
        <p className="text-sm text-warm-400 text-center py-8">暂无趋势数据</p>
      </div>
    );
  }

  return (
    <div className={`card p-5 ${className}`}>
      <h3 className="text-sm font-semibold text-warm-900 mb-4">
        📈 历年进面均分趋势
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ebe7e2" />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 12, fill: "#9b9184" }}
            tickFormatter={(v) => `${v}年`}
          />
          <YAxis
            domain={["dataMin - 5", "dataMax + 5"]}
            tick={{ fontSize: 11, fill: "#b8b0a5" }}
          />
          <Tooltip
            contentStyle={{
              borderRadius: "0.75rem",
              border: "1px solid #ebe7e2",
              boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
              fontSize: "12px",
            }}
            formatter={(value: number) => [`${value.toFixed(1)} 分`, "平均进面分"]}
            labelFormatter={(label) => `${label} 年`}
          />
          <Line
            type="monotone"
            dataKey="avg_score"
            stroke="#1e6b4e"
            strokeWidth={2.5}
            dot={{ fill: "#1e6b4e", r: 4 }}
            activeDot={{ r: 6, fill: "#1e6b4e" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
