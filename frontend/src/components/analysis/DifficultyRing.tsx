interface DifficultyRingProps {
  score: number;       // 0-100
  tier: "保底" | "稳妥" | "冲刺";
  size?: number;       // default 72
}

const TIER_STYLE: Record<string, { stroke: string; bg: string; text: string }> = {
  "保底": { stroke: "#16a34a", bg: "#dcfce7", text: "text-emerald-600" },
  "稳妥": { stroke: "#d97706", bg: "#fef3c7", text: "text-amber-600" },
  "冲刺": { stroke: "#dc2626", bg: "#fee2e2", text: "text-red-600" },
};

export default function DifficultyRing({ score, tier, size = 72 }: DifficultyRingProps) {
  const style = TIER_STYLE[tier] || TIER_STYLE["稳妥"];
  const radius = (size - 6) / 2;
  const circumference = radius * Math.PI * 2;
  const dashOffset = circumference * (1 - score / 100);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        className="transform -rotate-90"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="5"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={style.stroke}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-lg font-bold ${style.text}`}>{Math.round(score)}</span>
        <span className="text-[10px] text-warm-400 leading-none mt-0.5">{tier}</span>
      </div>
    </div>
  );
}
