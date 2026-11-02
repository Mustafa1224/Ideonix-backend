"""API contracts. Every stage of the pipeline takes and returns one of these models.
Teammates build against these shapes; FastAPI turns them into the /docs page."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------- auth / profile ----------


class SignupIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Profile(BaseModel):
    skills: list[str] = []
    interests: list[str] = []
    collaboration_preferences: list[str] = []


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    profile: Profile


# ---------- stage 1: idea understanding (Gemini) ----------


class IdeaUnderstanding(BaseModel):
    keywords: list[str]
    category: str
    target_users: list[str]
    problem_statement: str
    proposed_solution: str
    core_features: list[str]
    clarifying_questions: list[str] = []


# ---------- stage 2/3: competitors and reviews (Play Store) ----------


class Competitor(BaseModel):
    app_id: str
    name: str
    rating: float
    installs: int
    relevance: Literal["high", "medium", "low"] = "medium"
        # filled from real Google Play data and the NLP matching stage
    match_category: Optional[str] = None  # Exact Match / Strong Match / Partial Match
    match_score: Optional[float] = None  # 0 to 1
    summary: Optional[str] = None
    feature_keywords: list[str] = []
    store_url: Optional[str] = None
    icon: Optional[str] = None
    developer: Optional[str] = None
    genre: Optional[str] = None


class Review(BaseModel):
    app_id: str
    text: str
    rating: int = Field(ge=1, le=5)


class SampleReview(BaseModel):
    app_name: str
    text: str
    rating: int
    sentiment: str  # Positive / Neutral / Negative, from the star rating
    source: str = "Google Play"

# ---------- stage 4: review analysis (Divyanshi's NLP) ----------


class Gap(BaseModel):
    title: str
    missing_feature: str
    mentions: int
    competitors: list[str]
    quotes: list[str]


class ReviewAnalysis(BaseModel):
    review_count: int
    avg_sentiment: float = Field(ge=-1, le=1)  # -1 very negative, +1 very positive
    gaps: list[Gap]
    sentiment_split: dict[str, int] = {}  # Positive / Neutral / Negative review counts


# ---------- stage 5: score and verdict ----------


class OpportunityScore(BaseModel):
    total: int = Field(ge=0, le=100)
    verdict: Literal["Build", "Pivot", "Avoid"]
    demand: int
    user_pain: int
    gap_size: int
    competition_strength: int
    confidence: Literal["low", "medium", "high"]


# ---------- stage 6: feature evaluation (Gemini) ----------


class FeatureEvaluation(BaseModel):
    feature: str
    benefits: list[str]
    drawbacks: list[str]
    feasibility: Literal["easy", "moderate", "hard"]
    risks: list[str]


# ---------- stage 7: roadmap (Gemini) ----------


class RoadmapStep(BaseModel):
    order: int
    title: str
    description: str
    skills: list[str]
    est_days: int


class Roadmap(BaseModel):
    mvp_features: list[str]
    steps: list[RoadmapStep]
    tech_options: list[str]
    dependencies: list[str]
    risks: list[str]
    testing_steps: list[str]


# ---------- final result + API responses ----------


class AnalysisResult(BaseModel):
    idea: IdeaUnderstanding
    matches_status: str = "matches_found"  # or no_meaningful_match
    matches_message: Optional[str] = None
    sample_reviews: list[SampleReview] = []
    competitors: list[Competitor]
    review_analysis: ReviewAnalysis
    score: OpportunityScore
    feature_evaluations: list[FeatureEvaluation]
    roadmap: Roadmap


class AnalyzeIn(BaseModel):
    idea_text: str = Field(min_length=10, max_length=2000)


class AnalysisStatus(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: Optional[str] = None
    error: Optional[str] = None


class AnalysisOut(AnalysisStatus):
    idea_text: str
    created_at: datetime
    result: Optional[dict] = None  # partial while running, full AnalysisResult when completed


class AnalysisSummary(BaseModel):
    id: str
    idea_text: str
    status: str
    verdict: Optional[str] = None
    score: Optional[int] = None
    created_at: datetime
