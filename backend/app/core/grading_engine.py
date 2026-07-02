"""
申论批改核心引擎 — Essay Grading Engine.

Pipeline:
  1. RAG retrieval: fetch exam context, Hunan policies, model essays
  2. Build grading prompt with structured scoring dimensions
  3. Call DeepSeek for multi-dimensional evaluation
  4. Parse and return structured grading result
"""

from dataclasses import dataclass, field

from app.core.rag import get_rag
from app.core.llm_client import chat_json

# ============================================================
# Scoring dimensions — weighted rubric for 湖南申论
# ============================================================

DIMENSIONS = [
    {"key": "argument", "name": "立意观点", "weight": 0.25, "max_score": 10,
     "desc": "是否切题、立场正确、观点鲜明有深度"},
    {"key": "structure", "name": "结构逻辑", "weight": 0.20, "max_score": 10,
     "desc": "层次是否清晰、论证是否严密、过渡是否自然"},
    {"key": "content", "name": "内容论据", "weight": 0.25, "max_score": 10,
     "desc": "论据是否充分、能否结合湖南实际、引用政策是否恰当"},
    {"key": "language", "name": "语言表达", "weight": 0.20, "max_score": 10,
     "desc": "语言是否规范流畅、简洁有力"},
    {"key": "format", "name": "格式规范", "weight": 0.10, "max_score": 10,
     "desc": "是否符合文体要求、字数是否合适"},
]

# ============================================================
# System prompt — 湖南省考阅卷专家角色
# ============================================================

SYSTEM_PROMPT = """你是一位经验丰富的湖南省公务员考试申论阅卷专家。你需要对考生的申论作答进行专业、细致的批改。

## 评分维度（各维度 0-10 分）

1. **立意观点** (权重 25%)：是否准确理解题目要求，立场是否正确，观点是否鲜明有深度
2. **结构逻辑** (权重 20%)：文章结构是否合理，层次是否清晰，论证推理是否严密
3. **内容论据** (权重 25%)：论据是否充实具体，能否结合给定资料和湖南实际，引用政策文件是否恰当
4. **语言表达** (权重 20%)：语言是否规范、流畅，表达是否简洁有力，是否符合机关公文风格
5. **格式规范** (权重 10%)：是否符合申论文体格式要求，字数是否在合理范围内

## 给定资料使用要求
- 评价时需关注考生是否准确理解并恰当运用给定资料
- 小题（概括归纳、综合分析、对策建议等）：作答需紧扣材料，从材料中提炼要点，不可脱离材料空谈
- 大作文（议论文/策论文）：重在立意高度和论证深度，材料作为背景参考而非刚性约束
- 无论小题还是大作文，都不可大段照抄材料

## 湖南考情特别关注
- 是否体现对"三高四新"、乡村振兴、长株潭一体化等湖南战略的了解
- 是否结合湖南本地实际案例
- 是否符合湖南省考申论的评分偏好

## 输出要求
你必须严格输出以下 JSON 格式（不要输出其他任何内容）：

{
  "total_score": 数字(0-100),
  "grade": "一类文/二类文/三类文/四类文",
  "dimensions": [
    {
      "key": "argument",
      "name": "立意观点",
      "score": 数字(0-10),
      "comment": "详细评语",
      "highlights": ["优点1", "优点2"],
      "issues": ["问题1", "问题2"]
    },
    ...（共5个维度）
  ],
  "overall_comment": "总体评价，200字以内",
  "strengths": ["整体优点1", "整体优点2"],
  "weaknesses": ["整体不足1", "整体不足2"],
  "suggestions": ["具体修改建议1", "具体修改建议2"],
  "model_revision": "针对问题段落的改写示范（100字左右）",
  "hunan_relevance": "对湖南考情契合度的评价（50字以内）"
}
"""


# ============================================================
# Data models
# ============================================================

@dataclass
class DimensionScore:
    key: str
    name: str
    score: float
    weight: float
    comment: str
    highlights: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class GradingResult:
    total_score: float
    grade: str
    dimensions: list[DimensionScore]
    overall_comment: str
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    model_revision: str
    hunan_relevance: str
    # RAG context used for grading
    rag_context: dict = field(default_factory=dict)


# ============================================================
# Engine
# ============================================================

class GradingEngine:
    """申论批改引擎 — orchestrates RAG + LLM for essay evaluation."""

    def grade(self, question: str, answer: str, material: str = "", use_rag: bool = True) -> GradingResult:
        """
        Grade an essay submission.

        Args:
            question: The exam question / prompt
            answer: The student's answer text
            material: Reference material / source text for the essay (给定资料)
            use_rag: Whether to enrich the prompt with RAG context

        Returns:
            Structured GradingResult with scores, feedback, and suggestions
        """
        rag_context = {}
        if use_rag:
            try:
                rag = get_rag()
                rag_context = rag.retrieve_for_grading(
                    essay_topic=question[:200],
                    top_k_per_type=2,
                )
            except Exception:
                # RAG failure is non-fatal — grade without context
                rag_context = {}

        # Build the user prompt
        user_prompt = self._build_prompt(question, answer, material, rag_context)

        # Call DeepSeek
        raw = chat_json(SYSTEM_PROMPT, user_prompt)

        # Parse and validate
        return self._parse_result(raw, rag_context)

    # -------- Private helpers --------

    def _build_prompt(
        self,
        question: str,
        answer: str,
        material: str,
        rag_context: dict,
    ) -> str:
        """Construct the complete grading prompt."""
        parts = []
        # Reference material (给定资料) — the foundation for essay answers
        if material and material.strip():
            parts.append(f"## 给定资料（申论材料）\n\n{material}")

        parts.append(f"## 申论题目\n\n{question}")

        if material and material.strip():
            parts.append("（注：小题作答应紧扣材料，大作文以材料为参考背景，重在独立立意与论证）")

        parts.append(f"## 考生作答\n\n{answer}")

        # Inject RAG context if available
        if rag_context.get("exam_context"):
            parts.append("## 参考：题目相关标准答案/评分标准")
            for ctx in rag_context["exam_context"][:2]:
                parts.append(f"- {ctx['content'][:500]}")

        if rag_context.get("policy_context"):
            parts.append("## 参考：湖南相关政策文件")
            for ctx in rag_context["policy_context"][:2]:
                parts.append(f"- {ctx['content'][:500]}")

        if rag_context.get("model_context"):
            parts.append("## 参考：同类题型高分范文")
            for ctx in rag_context["model_context"][:1]:
                parts.append(f"- {ctx['content'][:500]}")

        parts.append("\n请按照要求对以上作答进行多维度评分和分析。")
        return "\n\n".join(parts)

    def _parse_result(self, raw: dict, rag_context: dict) -> GradingResult:
        """Parse the LLM JSON response into a GradingResult."""
        dims = []
        for d in raw.get("dimensions", []):
            dims.append(DimensionScore(
                key=d.get("key", ""),
                name=d.get("name", ""),
                score=float(d.get("score", 0)),
                weight=self._get_weight(d.get("key", "")),
                comment=d.get("comment", ""),
                highlights=d.get("highlights", []),
                issues=d.get("issues", []),
            ))

        return GradingResult(
            total_score=float(raw.get("total_score", 0)),
            grade=raw.get("grade", "未评分"),
            dimensions=dims,
            overall_comment=raw.get("overall_comment", ""),
            strengths=raw.get("strengths", []),
            weaknesses=raw.get("weaknesses", []),
            suggestions=raw.get("suggestions", []),
            model_revision=raw.get("model_revision", ""),
            hunan_relevance=raw.get("hunan_relevance", ""),
            rag_context=rag_context,
        )

    @staticmethod
    def _get_weight(key: str) -> float:
        for d in DIMENSIONS:
            if d["key"] == key:
                return d["weight"]
        return 0.0


# Singleton
_engine: GradingEngine | None = None


def get_grading_engine() -> GradingEngine:
    global _engine
    if _engine is None:
        _engine = GradingEngine()
    return _engine
