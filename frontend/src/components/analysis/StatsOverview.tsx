import { Target, TrendingDown, MapPin, Layers } from "lucide-react";
import type { StatsOverview as StatsOverviewType } from "../../services/api";

interface Props {
  stats: StatsOverviewType | null;
  matchedCount: number;
  totalCount: number;
  tierCounts: Record<string, number>;
}

export default function StatsOverview({ stats, matchedCount, totalCount, tierCounts }: Props) {
  const cards = [
    {
      icon: Target,
      label: "符合条件的岗位",
      value: `${matchedCount} / ${totalCount}`,
      sub: `${totalCount > 0 ? Math.round(matchedCount / totalCount * 100) : 0}% 可报考`,
      color: "text-brand-600",
      bg: "bg-brand-50",
    },
    {
      icon: TrendingDown,
      label: "最容易上岸的城市",
      value: stats?.easiest_city || "-",
      sub: stats?.by_city.find(c => c.city === stats.easiest_city)?.avg_score
        ? `平均进面 ${stats.by_city.find(c => c.city === stats.easiest_city)?.avg_score} 分`
        : "",
      color: "text-emerald-600",
      bg: "bg-emerald-50",
    },
    {
      icon: Layers,
      label: "保底 / 稳妥 / 冲刺",
      value: `🟢${tierCounts["保底"] || 0} 🟡${tierCounts["稳妥"] || 0} 🔴${tierCounts["冲刺"] || 0}`,
      sub: stats?.easiest_category ? `最容易类别: ${stats.easiest_category}` : "",
      color: "text-amber-600",
      bg: "bg-amber-50",
    },
    {
      icon: MapPin,
      label: "平均进面分",
      value: stats?.by_city.length
        ? `${Math.round(stats.by_city.reduce((s, c) => s + c.avg_score, 0) / stats.by_city.length)}`
        : "-",
      sub: "全省均值",
      color: "text-violet-600",
      bg: "bg-violet-50",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((card) => (
        <div key={card.label} className="card p-4">
          <div className={`w-8 h-8 rounded-xl ${card.bg} flex items-center justify-center mb-2`}>
            <card.icon className={`h-4 w-4 ${card.color}`} />
          </div>
          <div className="text-lg font-bold text-warm-900">{card.value}</div>
          <div className="text-[11px] text-warm-400 mt-0.5">{card.label}</div>
          {card.sub && <div className="text-[10px] text-warm-400 mt-0.5">{card.sub}</div>}
        </div>
      ))}
    </div>
  );
}
