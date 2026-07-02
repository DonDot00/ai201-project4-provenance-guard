LLM_WEIGHT = 0.65
STYLOMETRIC_WEIGHT = 0.35

AI_THRESHOLD = 0.75
HUMAN_THRESHOLD = 0.40


def combine_scores(llm_score: float, stylometric_score: float) -> float:
    """planning.md formula: combined = 0.65*llm_score + 0.35*stylometric_score."""
    combined = (LLM_WEIGHT * llm_score) + (STYLOMETRIC_WEIGHT * stylometric_score)
    return round(combined, 2)


def label_for_score(combined_score: float) -> str:
    if combined_score > AI_THRESHOLD:
        return "Likely AI-Generated"
    if combined_score < HUMAN_THRESHOLD:
        return "Likely Human-Written"
    return "Uncertain"
