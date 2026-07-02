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


def generate_label(combined_score: float) -> str:
    """Exact label text from planning.md's three transparency-label variants."""
    category = label_for_score(combined_score)

    if category == "Likely AI-Generated":
        pct = round(combined_score * 100)
        return (
            "This text is very likely AI-generated. Both our AI-writing check "
            "and our writing-pattern check point strongly in that direction. "
            f"Confidence: {pct}%."
        )

    if category == "Likely Human-Written":
        pct = round((1 - combined_score) * 100)
        return (
            "This text is very likely written by a person. Our checks found "
            f"natural, human-like writing patterns. Confidence: {pct}%."
        )

    return (
        "We can't be sure whether this text is AI-generated or human-written. "
        "Our checks gave mixed or weak signals. Please treat this result as a "
        "hint, not a final answer."
    )
