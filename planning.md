# Provenance Guard — Planning

## Architecture

Provenance Guard is a Flask backend with two flows: a **submission flow** and an **appeal flow**. When someone submits text to `POST /submit`, the app runs it through two independent detection signals, combines their scores into one confidence number, turns that number into a plain-language label, writes everything to an audit log, and sends the label and score back to the user. When someone disagrees with a result, `POST /appeal` creates an appeal tied to the original submission, marks it "under review," logs the appeal, and later logs the reviewer's final decision.

```
(a) Submission Flow

POST /submit
   | raw text
   v
[Signal 1: LLM Classifier]
   | signal 1 score (0-1, AI-likelihood)
   v
[Signal 2: Stylometric Heuristics]
   | signal 2 score (0-1, AI-likelihood)
   v
[Confidence Scorer]
   | combined score (0-1)
   v
[Transparency Label Generator]
   | label text
   v
[Audit Log]
   | (writes submission + scores + label)
   v
Response (label + confidence)


(b) Appeal Flow

POST /appeal
   | submission_id + reason
   v
[Status Update]
   | new status ("under_review")
   v
[Audit Log]
   | (writes appeal + status change)
   v
Response (appeal_id + status)
```

---

## Milestone 1 — Detection Signals & API Design

### Detection Signals (Overview)

**Signal 1: LLM-based classification (Groq / llama-3.3-70b-versatile)**
- **What it measures:** Asks the model to read the text and judge whether it sounds human or AI-written, based on patterns it has learned from huge amounts of text.
- **Why it differs between AI and human writing:** AI text tends to be smoother and more predictable. Human writing usually has more personal voice, quirks, and small imperfections.
- **Blind spot:** Can be fooled by AI text a human has edited, or by very polished human writing. It's a style guess, not proof.

**Signal 2: Stylometric heuristics (pure Python)**
- **What it measures:** Sentence length variance, type-token ratio (unique words vs. total words), and punctuation density.
- **Why it differs between AI and human writing:** Humans tend to vary sentence length and word choice more. AI text often has a steadier rhythm and more repeated patterns.
- **Blind spot:** Can't understand meaning or context. A very consistent human writer, or an AI told to "write more randomly," can slip past it.

### False-Positive Trace

If a human's writing gets wrongly flagged as AI: Signal 1 might lean "AI" because the writing is clean, while Signal 2 shows normal human-like variation. Because the signals disagree, the combined score should land low or "uncertain," not confident. The label should say something careful, like "Possibly AI-Generated (Low Confidence)," not a firm claim. The writer can then file an appeal, which gets logged and reviewed (see Appeals Workflow below).

### API Surface

- **POST /submit** — Input: `{ "text": "..." }` → Output: `{ "submission_id": "...", "label": "...", "confidence": 0.0-1.0, "signal_scores": { "llm": ..., "stylometry": ... } }`
- **POST /appeal** — Input: `{ "submission_id": "...", "reason": "..." }` → Output: `{ "appeal_id": "...", "status": "under_review" }`
- **GET /log** — Input: none → Output: `{ "entries": [ { "submission_id": "...", "label": "...", "confidence": ..., "timestamp": "..." }, ... ] }`

---

## Milestone 2 — Confidence Scoring, Transparency Labels & Appeals

### 1. Detection Signals — Implementation Detail

**Signal 1: LLM judgment (Groq)**
- Raw output: the prompt asks Groq for structured JSON: `{ "verdict": "ai" | "human", "self_confidence": 0.0-1.0 }`.
- Convert to a single 0-1 "AI-likelihood" score, `llm_score`, centered at 0.5:
  - If `verdict == "ai"`: `llm_score = 0.5 + (self_confidence / 2)`
  - If `verdict == "human"`: `llm_score = 0.5 - (self_confidence / 2)`
  - This maps a confident "AI" verdict close to 1.0, a confident "human" verdict close to 0.0, and a low-confidence verdict either way toward the 0.5 middle.

**Signal 2: Stylometric heuristics (pure Python)**
- Raw output: three sub-metrics, each normalized to 0-1:
  - `variance_score`: normalized sentence-length variance (low variance → AI-like)
  - `ttr_score`: type-token ratio, already 0-1 (low diversity → AI-like)
  - `punct_score`: how close punctuation density is to a "natural" human baseline range (big deviation → AI-like)
- Combine into a human-likeness score, then flip it to match the AI-likelihood direction:
  - `stylometric_human_score = (variance_score + ttr_score + punct_score) / 3`
  - `stylometric_score = 1 - stylometric_human_score`

**Combining both signals into one confidence score**
```
combined_score = round((0.65 * llm_score) + (0.35 * stylometric_score), 2)
```
- The LLM signal gets more weight (0.65) because it reads for meaning and context, not just surface patterns. Stylometry (0.35) acts as an independent, math-based check that can't be talked out of its answer the way a language model sometimes can.

### 2. Uncertainty Representation

**What a 0.6 score means to a user:** The system leans slightly toward "AI-generated," but not by enough to be sure. A 0.6 sits inside the "uncertain" band below — treat it as a hint, not a verdict.

**Calibration steps (raw signals → final score):**
1. Get `llm_score` from Signal 1 (converted from verdict + self-confidence).
2. Get `stylometric_score` from Signal 2 (averaged sub-metrics, flipped to AI-likelihood).
3. Clip both scores to the 0-1 range (guards against bad API output).
4. Apply the weighted formula above to get `combined_score`.
5. Round to 2 decimal places.
6. Map the rounded score to a label using the thresholds below.

**Thresholds (biased against false positives):**
| Combined Score | Label |
|---|---|
| > 0.75 | Likely AI-Generated |
| 0.40 – 0.75 | Uncertain |
| < 0.40 | Likely Human-Written |

The bar to call something "AI" is set high (0.75), while the bar to call something "human" is comparatively easy to clear (below 0.40). This is intentional: since the project's stated priority is to avoid falsely accusing a human writer, the system should need strong, high evidence before it commits to an "AI" label, but shouldn't need the same level of certainty to lean "human."

### 3. Transparency Label Design

**High-confidence AI (score > 0.75):**
> "This text is very likely AI-generated. Both our AI-writing check and our writing-pattern check point strongly in that direction. Confidence: [XX]%."

**High-confidence Human (score < 0.40):**
> "This text is very likely written by a person. Our checks found natural, human-like writing patterns. Confidence: [XX]%."

**Uncertain (0.40 – 0.75):**
> "We can't be sure whether this text is AI-generated or human-written. Our checks gave mixed or weak signals. Please treat this result as a hint, not a final answer."

`[XX]%` is `combined_score * 100` for the AI label, and `(1 - combined_score) * 100` for the human label, rounded to a whole number.

### 4. Appeals Workflow

- **Who can appeal:** The original submitter — identified by the `submission_id` returned from `POST /submit` (and an email or account ID, once auth exists).
- **What they submit:** `submission_id`, a written `reason` explaining why they think the label is wrong, and optionally a contact email.
- **What happens on receipt:**
  1. System creates a new `appeal_id`, linked to the `submission_id`.
  2. Appeal status is set to `"under_review"`.
  3. An audit log entry is written with: `appeal_id`, `submission_id`, `timestamp`, `reason`, and the original `label` + `confidence` at time of appeal (so reviewers can see what's being disputed without a second lookup).
- **Reviewer queue view:** A list of open appeals, each showing the submitted text (or a snippet), the original label and confidence, both signal scores, the appeal reason, current status, and an action to mark the appeal `"upheld"` or `"overturned"` — which also gets logged.

### 5. Edge Cases

1. **A human writes in a very uniform, controlled style** (e.g., technical writing, or a non-native English speaker sticking to simple, repeated sentence structures). Signal 2 sees low sentence-length variance and a lower type-token ratio (repeated domain terms) — both read as "AI-like." Signal 1 may agree, since the prose reads "too clean." Even with the anti-false-positive bias, a real human could land in the "Uncertain" band or worse.

2. **AI text run through a "humanizer" or lightly hand-edited** — someone adds typos, breaks up sentences, or shuffles a few words. Signal 2's variance and TTR scores shift toward "human-like," but Signal 1 may still catch AI patterns in meaning and structure. The two signals disagree, likely landing in "Uncertain" — which can let real AI content pass with a soft, non-alarming label if Signal 1's read isn't strong enough to outweigh Signal 2.

3. **Very short submissions** (a two- or three-sentence comment). Sentence-length variance and type-token ratio are close to meaningless on that little text — the stylometric score becomes noisy and can swing the combined score in either direction almost at random. Signal 1 also has very little to go on. Both signals get weaker together, so short text needs a minimum word-count guard, with the label caveated (e.g., "not enough text for a reliable check") when the guard trips.

---

## AI Tool Plan (Milestones 3–5)

### Milestone 3 — Core Detection & Scoring Implementation
- **Spec sections to hand over:** Architecture; Milestone 2 §1 (signal formulas) and §2 (calibration/thresholds).
- **What to ask the AI tool to generate:** the `POST /submit` Flask route, a Groq API wrapper that requests the structured `{verdict, self_confidence}` JSON, the three stylometric heuristic functions, the `combine_scores()` function implementing the weighted formula, and the threshold-to-label mapping function.
- **How I'll verify it:** run known obvious-AI and obvious-human text samples through it and hand-check the label; manually recompute `combined_score` for a couple of cases and compare to the code's output; confirm the Groq wrapper handles a malformed or slow API response without crashing the route.

### Milestone 4 — Appeals & Audit Log Implementation
- **Spec sections to hand over:** Milestone 2 §4 (appeals workflow); the appeal-flow half of the Architecture diagram.
- **What to ask the AI tool to generate:** the `POST /appeal` route, the appeal data model, the status-transition logic (`under_review` → `upheld`/`overturned`), the audit log writer, the `GET /log` route, and a simple reviewer queue endpoint/view.
- **How I'll verify it:** submit a real test appeal and confirm the status flips correctly; check that the audit log entry has every required field (`appeal_id`, `submission_id`, `timestamp`, `reason`, original label/confidence); walk through an uphold and an overturn to make sure both get logged.

### Milestone 5 — Testing, Edge Cases & Polish
- **Spec sections to hand over:** Milestone 2 §5 (edge cases); the full planning.md for context.
- **What to ask the AI tool to generate:** test cases for the three edge-case scenarios (uniform human writing, humanized AI text, short submissions), a minimum-word-count input guard, error handling for Groq API failures (e.g., fallback to stylometry-only with a note in the label), and a short demo script/README.
- **How I'll verify it:** run each edge-case text through the live system and judge by hand whether the output is reasonable; confirm the short-text guard triggers the "not enough text" caveat; simulate a Groq outage and confirm the app degrades gracefully instead of crashing.
