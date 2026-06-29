import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import {
  PenLine,
  Newspaper,
  BookOpen,
  BarChart3,
  ArrowRight,
  TrendingUp,
  Clock,
  FileText,
} from "lucide-react";

const features = [
  {
    icon: PenLine,
    title: "申论批改",
    desc: "AI 智能批改，五维度精准评分，逐段修改建议",
    href: "/essay",
    available: true,
    gradient: "from-emerald-500 to-teal-600",
    bg: "bg-emerald-50",
    iconColor: "text-emerald-600",
    stats: "已批改 2,680+ 篇",
  },
  {
    icon: Newspaper,
    title: "每日范文",
    desc: "按岗位类别精选范文，附亮点分析与要点提炼",
    href: "/daily",
    available: true,
    gradient: "from-amber-500 to-orange-600",
    bg: "bg-amber-50",
    iconColor: "text-amber-600",
    stats: "已收录 156 篇",
  },
  {
    icon: BookOpen,
    title: "行测刷题",
    desc: "五大模块专项练习，历年真题智能解析",
    href: "/xingce",
    available: false,
    gradient: "from-blue-500 to-indigo-600",
    bg: "bg-blue-50",
    iconColor: "text-blue-600",
    stats: "即将上线",
  },
  {
    icon: BarChart3,
    title: "考情分析",
    desc: "湖南历年分数线、报录比、命题趋势一网打尽",
    href: "/analysis",
    available: true,
    gradient: "from-violet-500 to-purple-600",
    bg: "bg-violet-50",
    iconColor: "text-violet-600",
    stats: "67 个岗位数据",
  },
];

// Quick stats for the hero section
const quickStats = [
  { label: "申论批改", value: "2,680+", sub: "篇已批改" },
  { label: "每日范文", value: "156", sub: "篇精选" },
  { label: "湖南真题", value: "48", sub: "套入库" },
];

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="space-y-8">
      {/* Hero section */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 via-brand-600 to-brand-800 p-6 md:p-10 text-white">
        {/* Decorative blobs */}
        <div className="absolute top-0 right-0 w-64 h-64 rounded-full bg-white/5 blur-3xl" />
        <div className="absolute bottom-0 left-1/2 w-48 h-48 rounded-full bg-brand-400/20 blur-3xl" />

        <div className="relative">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-xs font-medium bg-white/15 backdrop-blur text-white px-2.5 py-1 rounded-full">
              2026 湖南省考
            </span>
            <span className="text-xs text-brand-200">距公告发布还有 8 个月</span>
          </div>

          <h1 className="text-2xl md:text-3xl font-bold leading-tight tracking-tight">
            {getGreeting()}，{user?.display_name || user?.username}
            <br />
            今天也要加油备考 ✨
          </h1>
          <p className="text-brand-100 mt-3 max-w-lg text-sm md:text-base leading-relaxed">
            申论批改 + 每日范文两大功能已上线，更多备考工具正在赶来。
          </p>

          {/* Quick stats */}
          <div className="flex flex-wrap gap-4 md:gap-8 mt-6">
            {quickStats.map((s) => (
              <div key={s.label}>
                <div className="text-2xl font-bold">{s.value}</div>
                <div className="text-xs text-brand-200">{s.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Feature cards */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-warm-900">备考工具</h2>
          <button
            onClick={() => navigate("/essay/history")}
            className="text-sm text-warm-500 hover:text-brand-600 flex items-center gap-1 transition-colors"
          >
            <Clock className="h-3.5 w-3.5" />
            批改历史
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {features.map((f) => (
            <button
              key={f.title}
              onClick={() => f.available && navigate(f.href)}
              disabled={!f.available}
              className="group card p-5 text-left hover:shadow-elevated transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex gap-4 items-start"
            >
              <div
                className={`w-12 h-12 rounded-2xl ${f.bg} flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform`}
              >
                <f.icon className={`h-6 w-6 ${f.iconColor}`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-warm-900">{f.title}</h3>
                  {!f.available && (
                    <span className="text-[10px] bg-warm-100 text-warm-400 px-1.5 py-0.5 rounded-full">
                      即将上线
                    </span>
                  )}
                </div>
                <p className="text-sm text-warm-500 leading-relaxed mb-2">{f.desc}</p>
                <span className="text-xs text-warm-400">{f.stats}</span>
              </div>
              {f.available && (
                <ArrowRight className="h-4 w-4 text-warm-300 group-hover:text-brand-500 group-hover:translate-x-0.5 transition-all shrink-0 mt-1" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Essay CTA */}
        <div className="card p-6 bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-100/50">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="h-5 w-5 text-emerald-600" />
            <h3 className="font-semibold text-warm-900">开始申论批改</h3>
          </div>
          <p className="text-sm text-warm-600 mb-4">
            粘贴题目和作答，AI 将从立意、结构、内容、语言、格式五个维度评分
          </p>
          <button onClick={() => navigate("/essay")} className="btn-primary bg-emerald-600 hover:bg-emerald-700 text-sm py-2">
            立即批改
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>

        {/* Daily essay CTA */}
        <div className="card p-6 bg-gradient-to-br from-amber-50 to-orange-50 border-amber-100/50">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-5 w-5 text-amber-600" />
            <h3 className="font-semibold text-warm-900">今日范文推荐</h3>
          </div>
          <p className="text-sm text-warm-600 mb-4">
            按行政执法、县乡基层、省市直分类，每日更新精选申论范文
          </p>
          <button onClick={() => navigate("/daily")} className="btn-primary bg-amber-600 hover:bg-amber-700 text-sm py-2">
            去阅读
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 9) return "早上好";
  if (h < 12) return "上午好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
}
