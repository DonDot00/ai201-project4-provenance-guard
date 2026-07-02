# Provenance Guard

A Flask backend that classifies submitted text as AI-generated or human-written, scores its own confidence, shows a plain-language transparency label, and lets creators appeal a result they disagree with.

## 1. Architecture Overview

A submission starts at `POST /submit`, which takes raw `text` and a `creator_id`. The text is run through two independent detection signals: an LLM judgment call from Groq (`llama-3.3-70b-versatile`), and a pure-Python stylometric check (sentence-length variance, type-token ratio, punctuation density). Both signals return a 0-1 AI-likelihood score. Those two scores are combined into a single confidence score, which is mapped to one of three transparency labels. Every submission — content ID, creator, both signal scores, the combined score, and the label — gets written to an append-only audit log. The label, confidence, and both signal breakdowns are returned in the response.

If a creator disagrees with their result, `POST /appeal` takes their `content_id` and a written `creator_reasoning`. The system looks up the original submission in the audit log, writes a new appeal entry (linked to that submission, with the original label and confidence attached for context), and marks it `under_review`. `GET /log` returns the most recent entries — both submissions and appeals — so the full history is inspectable in one place.

## 2. Detection Signals

**Signal 1 — LLM judgment (Groq, llama-3.3-70b-versatile).** Asks the model to read the text and judge whether it sounds human or AI-written, based on patterns it's learned from large amounts of text. AI-generated text tends to be smoother and more predictable; human writing usually carries more personal voice and small imperfections. Blind spot: it's a style guess, not proof — it can be fooled by AI text a human has lightly edited, or by very polished, formal human writing.

**Signal 2 — Stylometric heuristics (pure Python).** Measures sentence-length variance, type-token ratio (unique words vs. total words), and punctuation density. Humans tend to vary sentence length and word choice more; AI text often holds a steadier rhythm and repeats patterns more. Blind spot: it can't read for meaning or context at all — a very consistent human writer, or AI text edited to sound looser, can slip past it in either direction.

## 3. Confidence Scoring

Both signals are converted to a 0-1 AI-likelihood score, then combined with a weighted average:

```
combined_score = (0.65 * llm_score) + (0.35 * stylometric_score)
```

The LLM signal is weighted higher because it reads for meaning; the stylometric signal acts as an independent, math-based check that can't be argued out of its answer.

**Validation process:** before wiring this into the endpoint, I ran it against four hand-picked inputs — one clearly AI-generated, one clearly human, and two borderline cases (a polished technical-writing sample and an AI paragraph lightly loosened to sound more casual) — and checked by hand that the combined score respected the stated thresholds and moved in the direction I'd expect for each case.

**Two real submissions, side by side:**

| | Sample A (personal/casual) | Sample B (formal/generic) |
|---|---|---|
| `llm_score` | 0.05 (verdict: human, self-confidence 0.9) | 0.9 (verdict: ai, self-confidence 0.8) |
| `stylometric_score` | 0.1426 | 0.3341 |
| `combined confidence` | **0.08** | **0.70** |
| `label` | Likely Human-Written (92%) | Uncertain |

Sample B is the more interesting result: the LLM was confident it was AI-generated, but the stylometric signal disagreed (high type-token ratio and "natural" punctuation density read as human-like), pulling the combined score down from 0.9 to 0.70 — just under the 0.75 bar for a confident AI label. That's the uncertainty design working as intended: two signals disagreeing produces a hedged result instead of a false confident claim.

## 4. Transparency Label

**High-confidence AI (score > 0.75):**
> "This text is very likely AI-generated. Both our AI-writing check and our writing-pattern check point strongly in that direction. Confidence: [XX]%."

**High-confidence Human (score < 0.40):**
> "This text is very likely written by a person. Our checks found natural, human-like writing patterns. Confidence: [XX]%."

**Uncertain (0.40 – 0.75):**
> "We can't be sure whether this text is AI-generated or human-written. Our checks gave mixed or weak signals. Please treat this result as a hint, not a final answer."

## 5. Rate Limiting

`POST /submit` is limited to **10 requests per minute** and **100 per day**, enforced with Flask-Limiter (`storage_uri="memory://"`).

Why these numbers: 10/minute comfortably covers a real writer submitting a handful of drafts, revisions, or excerpts in one sitting — nobody legitimately needs to fire off more than that in 60 seconds. It's low enough, though, to make a scripted flood of requests (someone probing the classifier or trying to brute-force a favorable result) visibly throttle almost immediately. 100/day covers a genuinely active user across a full day of writing sessions without feeling like a wall, while still bounding total Groq API spend per user per day to something predictable.

Real evidence — 12 rapid `POST /submit` calls against the running server:
```
request 1 -> 200
request 2 -> 200
request 3 -> 200
request 4 -> 200
request 5 -> 200
request 6 -> 200
request 7 -> 200
request 8 -> 200
request 9 -> 200
request 10 -> 200
request 11 -> 429
request 12 -> 429
```
Body of the `429` response:
```
429 Too Many Requests
10 per 1 minute
```

## 6. Known Limitations

The Sample B result above is a real, observed example of a specific failure mode: **formulaic-but-lexically-varied AI text fools the stylometric signal.** The stylometric heuristic assumes AI text repeats words and punctuation more predictably than human text — but a generic, corporate-sounding AI paragraph (the kind that avoids repeating the same word twice and uses conventional punctuation) can score *higher* on type-token ratio and "natural" punctuation density than plenty of real human writing. When that happens, Signal 2 actively drags a confident AI verdict from Signal 1 down into "Uncertain," understating how confident the system should actually be. This is a direct blind spot of using lexical-diversity and punctuation-density as human-likeness proxies — they measure surface variety, not authorship, and generic AI prose can have plenty of surface variety.

A second, related gap from planning: very short submissions (a two- or three-sentence comment) make sentence-length variance and type-token ratio statistically unreliable, since there's barely enough text to compute a meaningful variance or diversity ratio. This isn't yet guarded against with a minimum-length check.

## 7. Spec Reflection

I don't want to invent this for you — two questions to answer yourself:

- **Where did the spec (planning.md) genuinely help you?** Was there a moment building this where having the formula/thresholds/label text already nailed down in planning.md saved you from an ambiguous decision while coding, or kept two milestones consistent with each other?
- **Where did your implementation diverge from the spec, and why?** For example: planning.md's appeals workflow didn't fully define a "content storage" layer, and I ended up treating the audit log itself as the source of truth rather than adding a separate mutable store (see the M5 build notes above). Was there a place *you* changed course from what planning.md said, and what made you do it?

## 8. AI Usage

Also yours to fill in — I can't honestly write this section for you. Think back through the milestones:

- **Name two specific moments where you directed an AI tool to generate something and then had to revise or override its output.** (Not "I used AI to write code" in general — a specific instance. For example: did a generated formula/threshold need adjusting once you saw real output? Did a naming or schema choice it picked not match what you actually wanted, forcing a fix?)
- For each moment: what did you ask for, what came back, and what did you change and why?

---

**One more gap:** did you complete any stretch features beyond the five milestones (e.g. a reviewer queue view, persistence beyond the JSONL log, auth on `creator_id`)? If so, tell me what they are and I'll add a section for them.
