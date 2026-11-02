"""All prompts live here so the team can tune them without touching logic."""
import json

from .schemas import Gap, IdeaUnderstanding

IDEA_UNDERSTANDING = """You are a product analyst for Indian app markets.
The user wrote an app idea in English, Hindi or Hinglish. Extract the structure below.
Use English for keywords and category so they work as Google Play search terms.
If the idea is too vague to analyse, still fill every field with your best guess and list
what you would need to know in clarifying_questions.

Idea: {idea_text}"""

FEATURE_EVALUATION = """You are a senior product engineer advising an Indian student/startup team.
Idea: {idea}
Market gaps found in competitor reviews: {gaps}
For each proposed feature, give benefits, drawbacks, feasibility (easy/moderate/hard for a small
team in a few weeks) and risks. Be specific and honest; do not oversell."""

ROADMAP = """You are a technical lead planning an MVP for a small student team in India.
Idea: {idea}
Evaluated features: {features}
Produce an MVP roadmap: which features to ship first, ordered steps with required skills and rough
days, technology options, dependencies, risks and testing steps."""


def idea_prompt(idea_text: str) -> str:
    return IDEA_UNDERSTANDING.format(idea_text=idea_text)


def feature_prompt(idea: IdeaUnderstanding, gaps: list[Gap]) -> str:
    return FEATURE_EVALUATION.format(
        idea=idea.model_dump_json(),
        gaps=json.dumps([g.model_dump() for g in gaps[:8]]),
    )


def roadmap_prompt(idea: IdeaUnderstanding, features_json: str) -> str:
    return ROADMAP.format(idea=idea.model_dump_json(), features=features_json)
