import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search, User, MapPin, GraduationCap, Briefcase, ArrowRight, Loader2, Calendar, Filter } from "lucide-react";
import { analysisApi, type ProfileRequest, type CityItem, type YearItem } from "../../services/api";

const EDUCATIONS = ["大专", "本科", "硕士研究生", "博士研究生"];
const DEGREES = ["无", "学士", "硕士", "博士"];
const POLITICAL = ["群众", "共青团员", "中共党员", "中共党员（含预备党员）"];
const ORG_CATEGORIES = [
  { value: "省直机关及直属单位", label: "省直机关" },
  { value: "市州及以下机关", label: "市州及以下" },
  { value: "法院系统", label: "法院系统" },
  { value: "检察院系统", label: "检察院系统" },
  { value: "公安系统", label: "公安系统" },
  { value: "综合行政执法队伍", label: "行政执法队伍" },
];

const ESSAY_CATEGORIES = [
  { value: "省市卷", label: "省市卷" },
  { value: "县乡卷", label: "县乡卷" },
  { value: "行政执法卷", label: "行政执法卷" },
];

export default function FormPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [cities, setCities] = useState<CityItem[]>([]);
  const [years, setYears] = useState<YearItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  const [form, setForm] = useState<ProfileRequest>({
    birth_year: 1998,
    gender: "男",
    education: "本科",
    degree: "学士",
    major: "",
    political_status: "共青团员",
    work_experience_years: 0,
    preferred_cities: "",
    preferred_category: "",
    preferred_essay_category: "",
    exclude_professional_subject: false,
    year: 2026,
  });

  useEffect(() => {
    analysisApi.getYears().then(setYears).catch(() => {});
    analysisApi.getCities(form.year || 2026).then(setCities).catch(() => {});
    // Load existing profile
    analysisApi.getProfile().then((p) => {
      if (p.exists) {
        setForm({
          birth_year: p.birth_year,
          gender: p.gender,
          education: p.education,
          degree: p.degree,
          major: p.major,
          political_status: p.political_status,
          work_experience_years: p.work_experience_years,
          preferred_cities: p.preferred_cities,
          preferred_category: p.preferred_category,
          preferred_essay_category: p.preferred_essay_category,
        });
        setSaved(true);
      }
    }).catch(() => {});
  }, []);

  // Restore from URL params if present
  useEffect(() => {
    if (searchParams.toString()) {
      const restored: Partial<ProfileRequest> = {};
      const strKeys = ["gender","education","degree","major","political_status","preferred_cities","preferred_category","preferred_essay_category"];
      const numKeys = ["birth_year","work_experience_years","year"];
      strKeys.forEach(k => {
        const v = searchParams.get(k);
        if (v) (restored as any)[k] = v;
      });
      numKeys.forEach(k => {
        const v = searchParams.get(k);
        if (v) (restored as any)[k] = parseInt(v);
      });
      if (Object.keys(restored).length > 0) {
        setForm(prev => ({ ...prev, ...restored }));
      }
    }
  }, []);

  const update = (k: keyof ProfileRequest, v: any) => setForm({ ...form, [k]: v });

  const toggleCity = (code: string) => {
    const current = (form.preferred_cities || "").split(",").filter(Boolean);
    const idx = current.indexOf(code);
    if (idx >= 0) current.splice(idx, 1);
    else current.push(code);
    update("preferred_cities", current.join(","));
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const result = await analysisApi.recommend(form);
      // Persist form params to URL
      const params = new URLSearchParams();
      Object.entries(form).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== "") {
          params.set(k, String(v));
        }
      });
      navigate(`/analysis/result?${params.toString()}`, { state: result });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const selectedCities = (form.preferred_cities || "").split(",").filter(Boolean);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="page-heading flex items-center gap-2">
          <Search className="h-6 w-6 text-brand-500" />
          考情分析 · 岗位推荐
        </h1>
        <p className="page-subtitle">填写个人信息，AI 为你匹配最合适的岗位并预测进面分数</p>
        {saved && <p className="text-xs text-emerald-600 mt-1">已加载上次保存的画像</p>}
      </div>

      {/* Basic info */}
      {/* Year selector */}
      <div className="card p-4 flex items-center gap-4">
        <Calendar className="h-5 w-5 text-brand-500 shrink-0" />
        <span className="text-sm font-medium text-warm-700">考试年份</span>
        <div className="flex gap-2">
          {(years.length > 0 ? years : [{year:2026,count:0},{year:2025,count:0},{year:2024,count:0},{year:2023,count:0}]).map((y) => (
            <button key={y.year} onClick={() => { update("year", y.year); analysisApi.getCities(y.year).then(setCities).catch(() => {}); }}
              className={`text-sm px-4 py-1.5 rounded-lg border transition-all ${
                (form.year || 2026) === y.year
                  ? "bg-brand-500 text-white border-brand-500"
                  : "bg-white text-warm-600 border-warm-200 hover:border-brand-200"
              }`}>
              {y.year}年
            </button>
          ))}
        </div>
        <span className="text-xs text-warm-400 ml-auto">
          {form.year === 2026 ? "最新考年" : form.year === 2025 ? "上一年" : "历史参考"}
        </span>
      </div>

      {/* Basic info */}
      <div className="card p-6 space-y-5">
        <h2 className="font-semibold text-warm-900 flex items-center gap-2 text-sm">
          <User className="h-4 w-4 text-brand-500" /> 基本信息
        </h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-warm-500 mb-1.5">出生年份</label>
            <input type="number" value={form.birth_year || ""}
              onChange={(e) => update("birth_year", parseInt(e.target.value) || null)}
              className="input-field" placeholder="1998" />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-500 mb-1.5">性别</label>
            <div className="flex gap-2">
              {["男", "女"].map((g) => (
                <button key={g} onClick={() => update("gender", g)}
                  className={`flex-1 py-2 text-sm rounded-xl border transition-all ${
                    form.gender === g ? "bg-brand-50 border-brand-300 text-brand-700 font-medium" : "border-warm-200 text-warm-600 hover:border-warm-300"
                  }`}>{g}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-500 mb-1.5">学历</label>
            <select value={form.education || ""} onChange={(e) => update("education", e.target.value)}
              className="input-field">
              {EDUCATIONS.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-500 mb-1.5">学位</label>
            <select value={form.degree || ""} onChange={(e) => update("degree", e.target.value)}
              className="input-field">
              {DEGREES.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-warm-500 mb-1.5">
              <GraduationCap className="h-3.5 w-3.5 inline mr-1" />专业
            </label>
            <input type="text" value={form.major || ""}
              onChange={(e) => update("major", e.target.value)}
              className="input-field" placeholder="如：法学、会计学" />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-500 mb-1.5">政治面貌</label>
            <select value={form.political_status || ""}
              onChange={(e) => update("political_status", e.target.value)}
              className="input-field">
              {POLITICAL.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-500 mb-1.5">
              <Briefcase className="h-3.5 w-3.5 inline mr-1" />基层工作年限
            </label>
            <input type="number" value={form.work_experience_years || 0}
              onChange={(e) => update("work_experience_years", parseInt(e.target.value) || 0)}
              className="input-field" min={0} max={40} />
          </div>
        </div>
      </div>

      {/* Preferences */}
      <div className="card p-6 space-y-5">
        <h2 className="font-semibold text-warm-900 flex items-center gap-2 text-sm">
          <MapPin className="h-4 w-4 text-accent-500" /> 意向城市与岗位
        </h2>

        <div>
          <label className="block text-xs font-medium text-warm-500 mb-2">意向城市（可多选）</label>
          <div className="flex flex-wrap gap-2">
            {cities.map((c) => (
              <button key={c.code} onClick={() => toggleCity(c.code)}
                className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
                  selectedCities.includes(c.code)
                    ? "bg-brand-500 text-white border-brand-500"
                    : "bg-white text-warm-600 border-warm-200 hover:border-brand-200"
                }`}>
                {c.label} ({c.count})
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-warm-500 mb-2">意向岗位类别（组织系统）</label>
          <div className="flex flex-wrap gap-2">
            {ORG_CATEGORIES.map((c) => (
              <button key={c.value} onClick={() => update("preferred_category",
                form.preferred_category === c.value ? "" : c.value)}
                className={`text-sm px-4 py-2 rounded-xl border transition-all ${
                  form.preferred_category === c.value
                    ? "bg-brand-500 text-white border-brand-500"
                    : "bg-white text-warm-600 border-warm-200 hover:border-brand-200"
                }`}>{c.label}</button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-warm-500 mb-2">申论类别（考试卷类型）</label>
          <div className="flex gap-2">
            {ESSAY_CATEGORIES.map((c) => (
              <button key={c.value} onClick={() => update("preferred_essay_category",
                form.preferred_essay_category === c.value ? "" : c.value)}
                className={`text-sm px-4 py-2 rounded-xl border transition-all ${
                  form.preferred_essay_category === c.value
                    ? "bg-accent-500 text-white border-accent-500"
                    : "bg-white text-warm-600 border-warm-200 hover:border-accent-200"
                }`}>{c.label}</button>
            ))}
          </div>
        </div>

        <div>
          <button
            onClick={() => update("exclude_professional_subject", !form.exclude_professional_subject)}
            className={`flex items-center gap-2 text-sm px-4 py-2.5 rounded-xl border transition-all ${
              form.exclude_professional_subject
                ? "bg-emerald-50 border-emerald-300 text-emerald-700 font-medium"
                : "bg-white text-warm-500 border-warm-200 hover:border-emerald-200 hover:text-warm-700"
            }`}
          >
            <Filter className="h-4 w-4" />
            {form.exclude_professional_subject ? "✅ 仅看行测申论" : "📋 仅看行测申论"}
          </button>
          <p className="text-xs text-warm-400 mt-1.5">
            开启后排除加试公安基础知识、财经专业知识、法律专业科目等岗位
          </p>
        </div>
      </div>

      {/* Submit */}
      <button onClick={handleSubmit} disabled={loading}
        className="btn-accent w-full py-3 text-base">
        {loading ? (
          <><Loader2 className="h-5 w-5 animate-spin" /> 分析中...</>
        ) : (
          <>开始分析 <ArrowRight className="h-5 w-5" /></>
        )}
      </button>
    </div>
  );
}
