/** Centralized HTTP client with JWT handling. */

const BASE_URL = "/api";

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem("access_token", token);
    } else {
      localStorage.removeItem("access_token");
    }
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem("access_token");
    }
    return this.token;
  }

  async request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, ...rest } = options;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    // Allow callers to suppress Content-Type (e.g. FormData uploads)
    if (rest.headers && (rest.headers as Record<string, string>)["Content-Type"] === "") {
      delete headers["Content-Type"];
      delete (rest.headers as Record<string, string>)["Content-Type"];
    }

    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}${path}`, {
      ...rest,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401) {
      this.setToken(null);
      window.location.href = "/login";
      throw new Error("认证已过期，请重新登录");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "请求失败" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /** Upload a file with multipart/form-data — browser sets Content-Type with boundary. */
  async uploadFile<T = unknown>(
    path: string,
    file: File,
    extraFields?: Record<string, string | number>,
  ): Promise<T> {
    const formData = new FormData();
    formData.append("file", file);
    if (extraFields) {
      Object.entries(extraFields).forEach(([key, value]) => {
        formData.append(key, String(value));
      });
    }

    const headers: Record<string, string> = {};
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (response.status === 401) {
      this.setToken(null);
      window.location.href = "/login";
      throw new Error("认证已过期，请重新登录");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "请求失败" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  get<T = unknown>(path: string) {
    return this.request<T>(path, { method: "GET" });
  }

  post<T = unknown>(path: string, body?: unknown) {
    return this.request<T>(path, { method: "POST", body });
  }

  put<T = unknown>(path: string, body?: unknown) {
    return this.request<T>(path, { method: "PUT", body });
  }

  delete<T = unknown>(path: string) {
    return this.request<T>(path, { method: "DELETE" });
  }
}

export const api = new ApiClient();

// ---------- Auth types ----------

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  display_name?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  username: string;
  display_name: string | null;
}

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  display_name: string;
  created_at: string;
}

export const authApi = {
  login: (data: LoginRequest) => api.post<TokenResponse>("/auth/login", data),
  register: (data: RegisterRequest) => api.post<TokenResponse>("/auth/register", data),
  me: () => api.get<UserInfo>("/auth/me"),
};

// ---------- Essay grading types ----------

export interface DimensionScore {
  key: string;
  name: string;
  score: number;
  weight: number;
  comment: string;
  highlights: string[];
  issues: string[];
}

export interface GradingResult {
  essay_id: string;
  total_score: number;
  grade: string;
  dimensions: DimensionScore[];
  overall_comment: string;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  model_revision: string;
  hunan_relevance: string;
  status: string;
}

export interface GradeRequest {
  question: string;
  material: string;
  answer: string;
  use_rag: boolean;
}

export interface EssayHistoryItem {
  id: string;
  question: string;
  material?: string | null;
  total_score: number | null;
  grade: string | null;
  status: string;
  created_at: string;
}

export interface HistoryResponse {
  items: EssayHistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

export const essayApi = {
  grade: (data: GradeRequest) => api.post<GradingResult>("/essay/grade", data),
  getHistory: (page = 1, pageSize = 10) =>
    api.get<HistoryResponse>(`/essay/history?page=${page}&page_size=${pageSize}`),
  getResult: (essayId: string) => api.get<GradingResult>(`/essay/${essayId}`),
};

// ---------- Knowledge base types ----------

export interface SearchResult {
  id: string;
  content: string;
  metadata: Record<string, string>;
  score: number;
}

export interface SearchResponse {
  query: string;
  doc_type: string;
  total: number;
  results: SearchResult[];
}

export interface DocumentItem {
  id: string;
  title: string;
  doc_type: string;
  file_type: string;
  source_name: string;
  chunk_count: number;
  status: string;
  created_at: string;
}

export interface DocumentListResponse {
  documents: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface UploadDocumentResponse {
  id: string;
  title: string;
  doc_type: string;
  chunk_count: number;
  status: string;
}

export interface IngestItem {
  doc_type: string;
  title: string;
  content: string;
  source_url?: string;
  source_name?: string;
  topic?: string;
  exam_year?: number;
  category?: string;
  tags?: string[];
}

export interface IngestItemResult {
  index: number;
  title: string;
  doc_type: string;
  status: string;
  chunk_count: number;
  error: string | null;
}

export interface IngestResponse {
  total: number;
  ingested: number;
  skipped: number;
  errors: number;
  results: IngestItemResult[];
}

export const knowledgeApi = {
  search: (q: string, docType = "exam", topK = 5) =>
    api.get<SearchResponse>(`/knowledge/search?q=${encodeURIComponent(q)}&doc_type=${docType}&top_k=${topK}`),
  getDocuments: (page = 1, pageSize = 20, docType?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (docType) params.set("doc_type", docType);
    return api.get<DocumentListResponse>(`/knowledge/documents?${params}`);
  },
  /** Upload a document file (PDF/MD/TXT) with metadata. */
  uploadDocument: (file: File, docType: string, title: string, sourceUrl = "", sourceName = "") =>
    api.uploadFile<UploadDocumentResponse>("/knowledge/upload", file, {
      doc_type: docType,
      title,
      source_url: sourceUrl,
      source_name: sourceName,
    }),
  /** Delete a document (PostgreSQL + ChromaDB). */
  deleteDocument: (docId: string) =>
    api.delete<void>(`/knowledge/documents/${docId}`),
  /** Bulk ingest items from crawler pipeline. */
  ingestItems: (items: IngestItem[]) =>
    api.post<IngestResponse>("/knowledge/ingest", { items }),
};

// ---------- Daily Essay types ----------

export interface DailyEssayOut {
  id: string;
  title: string;
  content: string;
  topic: string | null;
  source_name: string | null;
  source_url: string | null;
  exam_category: string;
  recommend_date: string;
  highlights: string | null;
  key_points: string | null;
  view_count: number;
}

export interface DailyEssayListItem {
  id: string;
  title: string;
  topic: string | null;
  source_name: string | null;
  exam_category: string;
  recommend_date: string;
  highlights: string | null;
}

export interface DailyListResponse {
  items: DailyEssayListItem[];
  total: number;
}

export interface TodayResponse {
  date: string;
  essays: DailyEssayOut[];
  categories_available: string[];
}

export interface TopicItem {
  topic: string;
  count: number;
}

export interface CategoryInfo {
  category: string;
  count: number;
  label: string;
}

export interface RefreshResponse {
  started: boolean;
  message: string;
}

export const dailyApi = {
  getToday: (category?: string) => {
    const params = category ? `?category=${encodeURIComponent(category)}` : "";
    return api.get<TodayResponse>(`/daily/today${params}`);
  },
  getArchive: (page = 1, pageSize = 12, topic?: string, category?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (topic) params.set("topic", topic);
    if (category) params.set("category", category);
    return api.get<DailyListResponse>(`/daily/archive?${params}`);
  },
  getTopics: () => api.get<TopicItem[]>("/daily/topics"),
  getCategories: () => api.get<CategoryInfo[]>("/daily/categories"),
  getDetail: (id: string) => api.get<DailyEssayOut>(`/daily/${id}`),
  refresh: (useAi = true) => api.post<RefreshResponse>(`/daily/refresh?use_ai=${useAi}`),
};

// ---------- Analysis types ----------

export interface ProfileRequest {
  birth_year?: number | null;
  gender?: string | null;
  education?: string | null;
  degree?: string | null;
  major?: string | null;
  political_status?: string | null;
  work_experience_years?: number | null;
  preferred_cities?: string | null;
  preferred_category?: string | null;  // now matches org_category (组织系统类别)
  preferred_essay_category?: string | null;  // 申论类别：省市卷 / 县乡卷 / 行政执法卷
  exclude_professional_subject?: boolean;
  year?: number;
}

export interface DifficultyBreakdown {
  admission_score: number;
  competition_ratio: number;
  enrollment_scale: number;
  trend_adjustment: number;
  total: number;
}

export interface PositionOut {
  id: string;
  year: number;
  city: string;
  city_label: string;
  district: string | null;
  department: string;
  position_name: string;
  exam_category: string;
  org_category: string | null;  // 组织系统类别
  education_requirement: string;
  degree_requirement: string;
  major_requirement: string | null;
  political_requirement: string;
  gender_requirement: string;
  experience_requirement: string;
  age_limit: string;
  exam_subject: string | null;
  enrollment_count: number;
  applicant_count: number | null;
  competition_ratio: number | null;
  min_score_interview: number | null;
  max_score_interview: number | null;
  avg_score_interview: number | null;
  interview_ratio: string;
  match_score: number;
  match_details: string[];
  risk_level: string;
  predicted_score: number | null;
  difficulty_score: number;
  difficulty_breakdown: DifficultyBreakdown;
  tier: string;
}

export interface AnalysisResult {
  profile: ProfileRequest;
  total_positions: number;
  matched_positions: number;
  recommendations: PositionOut[];
  summary: string;
}

export interface CityItem { code: string; label: string; count: number; }
export interface YearItem { year: number; count: number; }

export interface TrendDataPoint {
  year: number;
  avg_score: number;
  count: number;
}

export interface CityTrend {
  city: string;
  category: string | null;
  data: TrendDataPoint[];
}

export interface StatsByItem {
  city?: string;
  category?: string;
  avg_score: number;
  count: number;
}

export interface StatsOverview {
  by_city: StatsByItem[];
  by_category: StatsByItem[];
  easiest_city: string;
  easiest_category: string;
}

export interface ImportResult {
  success: boolean;
  total_rows: number;
  created: number;
  updated: number;
  skipped: number;
  not_found: number;
  errors: Array<{ row?: number; sheet?: string; department?: string; position_name?: string; message: string }>;
}

export const analysisApi = {
  recommend: (data: ProfileRequest) => api.post<AnalysisResult>("/analysis/recommend", data),
  getProfile: () => api.get<{ exists: boolean } & ProfileRequest>("/analysis/profile"),
  getCities: (year?: number) => api.get<CityItem[]>(`/analysis/cities${year ? `?year=${year}` : ""}`),
  getYears: () => api.get<YearItem[]>("/analysis/years"),
  getTrend: (city: string, category?: string) =>
    api.get<CityTrend>(`/analysis/trend/${city}${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  getStats: () =>
    api.get<StatsOverview>("/analysis/stats/overview"),
  /** Import position Excel (.xlsx) — multi-sheet supported. */
  importPositions: (file: File, year: number) =>
    api.uploadFile<ImportResult>("/analysis/import/positions", file, { year }),
  /** Import interview score Excel (.xlsx). */
  importScores: (file: File, year: number) =>
    api.uploadFile<ImportResult>("/analysis/import/scores", file, { year }),
};
