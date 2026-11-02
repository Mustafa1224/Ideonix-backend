import json

from . import gemini_client, prompts
from .schemas import FeatureEvaluation, IdeaUnderstanding, Roadmap


def build_roadmap(idea: IdeaUnderstanding, evaluations: list[FeatureEvaluation]) -> Roadmap:
    features_json = json.dumps([e.model_dump() for e in evaluations])
    return gemini_client.generate_structured(prompts.roadmap_prompt(idea, features_json), Roadmap)