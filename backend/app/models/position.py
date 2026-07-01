"""Historical exam position data — 历年岗位进面分数线."""

from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import gen_uuid


class PositionHistory(Base):
    """One row = one position in one exam year."""

    __tablename__ = "position_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)

    # Exam info
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    province: Mapped[str] = mapped_column(String(20), default="湖南")

    # Location
    city: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 长沙/株洲/省直...
    district: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Position info
    department: Mapped[str] = mapped_column(String(200), nullable=False)  # 单位名称
    position_name: Mapped[str] = mapped_column(String(200), nullable=False)  # 岗位名称
    position_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Category
    exam_category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # 行政执法 / 县乡基层 / 省市直 / 综合通用
    org_category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # 组织系统类别（Excel sheet名）：省直机关及直属单位 / 市州及以下机关 / 法院系统 / 检察院系统 / 公安系统 / 综合行政执法队伍

    # Requirements
    education_requirement: Mapped[str] = mapped_column(String(20), default="本科及以上")
    # 大专及以上 / 本科及以上 / 硕士研究生及以上
    degree_requirement: Mapped[str] = mapped_column(String(20), default="学士")
    # 无要求 / 学士 / 硕士 / 博士
    major_requirement: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 专业要求（逗号分隔），null 表示不限
    political_requirement: Mapped[str] = mapped_column(String(20), default="不限")
    # 不限 / 中共党员 / 中共党员（含预备党员）
    gender_requirement: Mapped[str] = mapped_column(String(10), default="不限")
    # 不限 / 男性 / 女性
    experience_requirement: Mapped[str] = mapped_column(String(20), default="不限")
    # 不限 / 2年以上基层工作经历
    age_limit: Mapped[str] = mapped_column(String(20), default="35周岁以下")
    # 35周岁以下 / 30周岁以下 / 25周岁以下
    exam_subject: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 笔试考试科目：行测、申论（省市卷）/ 行测、申论（县乡卷）/ 行测、申论（行政执法卷）

    # Score data
    min_score_interview: Mapped[float] = mapped_column(Float, nullable=True)
    # 最低进面分
    max_score_interview: Mapped[float] = mapped_column(Float, nullable=True)
    # 最高进面分（如果有）
    avg_score_interview: Mapped[float] = mapped_column(Float, nullable=True)
    # 平均进面分

    # Competition data
    enrollment_count: Mapped[int] = mapped_column(Integer, default=1)  # 招录人数
    applicant_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 报名人数
    interview_ratio: Mapped[str] = mapped_column(String(10), default="1:3")  # 面试比例

    # Meta
    source: Mapped[str] = mapped_column(String(100), default="湖南人事考试网")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def competition_ratio(self) -> float | None:
        """报名竞争比"""
        if self.applicant_count and self.enrollment_count:
            return round(self.applicant_count / self.enrollment_count, 1)
        return None

    @property
    def city_label(self) -> str:
        cities = {
            "省直": "省直机关",
            "长沙": "长沙市", "株洲": "株洲市", "湘潭": "湘潭市",
            "衡阳": "衡阳市", "邵阳": "邵阳市", "岳阳": "岳阳市",
            "常德": "常德市", "张家界": "张家界市", "益阳": "益阳市",
            "郴州": "郴州市", "永州": "永州市", "怀化": "怀化市",
            "娄底": "娄底市", "湘西": "湘西州",
        }
        return cities.get(self.city, self.city)

    def __repr__(self) -> str:
        return f"<Position {self.year} {self.city} {self.position_name}>"


class UserProfile(Base):
    """User profile for position matching — 用户画像."""

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )

    # 基本信息
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(5), nullable=True)  # 男/女
    education: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 大专 / 本科 / 硕士研究生 / 博士研究生
    degree: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 无 / 学士 / 硕士 / 博士
    major: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 专业名称
    political_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 群众 / 共青团员 / 中共党员 / 中共党员（含预备党员）
    work_experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 基层工作年限

    # 偏好
    preferred_cities: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 意向城市（逗号分隔）
    preferred_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 意向岗位类别（现在匹配 org_category）
    preferred_essay_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 意向申论类别：省市卷 / 县乡卷 / 行政执法卷

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
