import re

# ASSUMPTIONS (planning.md describes direction, not exact constants — flagged
# here so they're easy to find and tune):
#   - Sentence-length variance is expressed as a coefficient of variation
#     (stdev / mean), capped at 1.0 to count as "fully varied" (human-like).
#   - "Natural" punctuation density is treated as 0.08-0.20 marks per word;
#     deviation beyond that is normalized against a 0.20 cap.


def _sentence_lengths(text):
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences if s.strip()]
    return [length for length in lengths if length > 0]


def _variance_score(text):
    lengths = _sentence_lengths(text)
    if len(lengths) < 2:
        return 0.5  # not enough sentences to measure variance reliably
    mean_len = sum(lengths) / len(lengths)
    variance = sum((length - mean_len) ** 2 for length in lengths) / len(lengths)
    cv = (variance ** 0.5) / mean_len
    return min(cv, 1.0)


def _ttr_score(text):
    words = re.findall(r"\b\w+\b", text.lower())
    if not words:
        return 0.5
    return len(set(words)) / len(words)


def _punctuation_score(text):
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 0.5
    punct_count = len(re.findall(r"[.,!?;:]", text))
    density = punct_count / len(words)

    low, high = 0.08, 0.20
    if low <= density <= high:
        deviation = 0.0
    elif density < low:
        deviation = low - density
    else:
        deviation = density - high

    max_deviation = 0.20
    return max(0.0, 1.0 - min(deviation / max_deviation, 1.0))


def get_stylometric_signal(text: str) -> dict:
    """Signal 2: pure-Python stylometric heuristics.

    Each sub-metric is 0-1 where higher = more human-like. They're averaged
    into a human-likeness score, then flipped to match Signal 1's
    AI-likelihood direction, per planning.md.
    """
    variance_score = _variance_score(text)
    ttr_score = _ttr_score(text)
    punct_score = _punctuation_score(text)

    human_score = (variance_score + ttr_score + punct_score) / 3
    stylometric_score = round(1 - human_score, 4)

    return {
        "variance_score": round(variance_score, 4),
        "ttr_score": round(ttr_score, 4),
        "punct_score": round(punct_score, 4),
        "stylometric_score": stylometric_score,
    }


if __name__ == "__main__":
    sample = (
        "The cat sat on the mat. It watched the rain. Outside, the wind was "
        "picking up, and everything felt calm."
    )
    print(get_stylometric_signal(sample))
