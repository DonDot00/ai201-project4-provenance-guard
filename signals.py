import json
import os

from groq import Groq

_client = None

SYSTEM_PROMPT = (
    "You are a writing-style analyst. Read the text and judge whether it reads "
    "as human-written or AI-generated. Respond with ONLY a JSON object in this "
    'exact form: {"verdict": "human" | "ai", "self_confidence": <0.0-1.0>}. '
    "self_confidence is how sure you are in your verdict."
)


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def get_llm_signal(text: str) -> dict:
    """Signal 1: ask llama-3.3-70b-versatile (via Groq) to judge human vs AI authorship.

    Per planning.md, this signal's raw output is a binary verdict plus a
    self-reported confidence, which gets converted into a single 0-1
    AI-likelihood score (llm_score) centered at 0.5.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = json.loads(response.choices[0].message.content)
    verdict = raw["verdict"]
    self_confidence = float(raw["self_confidence"])

    if verdict == "ai":
        llm_score = 0.5 + (self_confidence / 2)
    else:
        llm_score = 0.5 - (self_confidence / 2)

    return {
        "verdict": verdict,
        "self_confidence": self_confidence,
        "llm_score": round(llm_score, 4),
    }


if __name__ == "__main__":
    # Quick standalone check: python signals.py
    sample = "The cat sat on the mat and watched the rain fall outside the window."
    print(get_llm_signal(sample))

