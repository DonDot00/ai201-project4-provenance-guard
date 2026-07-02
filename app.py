import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from audit_log import find_submission, get_log, log_appeal, log_submission
from confidence import combine_scores, generate_label
from signals import get_llm_signal
from stylometry import get_stylometric_signal

load_dotenv()

app = Flask(__name__)

limiter = Limiter(get_remote_address, app=app, storage_uri="memory://", default_limits=[])


@app.post("/submit")
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    creator_id = data.get("creator_id")

    if not text or not creator_id:
        return jsonify({"error": "text and creator_id are required"}), 400

    content_id = str(uuid.uuid4())
    signal1 = get_llm_signal(text)
    signal2 = get_stylometric_signal(text)

    confidence = combine_scores(signal1["llm_score"], signal2["stylometric_score"])
    label = generate_label(confidence)

    log_submission(
        content_id=content_id,
        creator_id=creator_id,
        attribution=signal1["verdict"],
        confidence=confidence,
        llm_score=signal1["llm_score"],
        stylometric_score=signal2["stylometric_score"],
        label=label,
        status="processed",
    )

    return jsonify(
        {
            "content_id": content_id,
            "attribution": signal1,
            "stylometry": signal2,
            "confidence": confidence,
            "label": label,
        }
    )


@app.post("/appeal")
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id or not creator_reasoning:
        return jsonify({"error": "content_id and creator_reasoning are required"}), 400

    original = find_submission(content_id)
    if original is None:
        return jsonify({"error": "content_id not found"}), 404

    appeal_id = str(uuid.uuid4())
    log_appeal(
        appeal_id=appeal_id,
        content_id=content_id,
        creator_reasoning=creator_reasoning,
        original_attribution=original["attribution"],
        original_confidence=original["confidence"],
        original_label=original["label"],
    )

    return jsonify({"appeal_id": appeal_id, "content_id": content_id, "status": "under_review"})


@app.get("/log")
def log():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"entries": get_log(limit=limit)})


if __name__ == "__main__":
    app.run(debug=True)
