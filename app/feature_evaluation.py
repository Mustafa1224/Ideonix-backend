from pydantic import BaseModel

from . import gemini_client, prompts
from .schemas import FeatureEvaluation, Gap, IdeaUnderstanding


class _FeatureList(BaseModel):  # wrapper so the AI returns one JSON object
    evaluations: list[FeatureEvaluation]


def evaluate_features(idea: IdeaUnderstanding, gaps: list[Gap]) -> list[FeatureEvaluation]:
    return gemini_client.generate_structured(prompts.feature_prompt(idea, gaps), _FeatureList).evaluations