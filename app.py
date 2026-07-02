import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from audit_log import get_log, log_submission
from confidence import combine_scores, label_for_score
from signals import get_llm_signal
from stylometry import get_stylometric_signal

load_dotenv()

app = Flask(__name__)


@app.post("/submit")
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
    label = label_for_score(confidence)

    log_submission(
        content_id=content_id,
        creator_id=creator_id,
        attribution=signal1["verdict"],
        confidence=confidence,
        llm_score=signal1["llm_score"],
        stylometric_score=signal2["stylometric_score"],
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


@app.get("/log")
def log():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"entries": get_log(limit=limit)})


if __name__ == "__main__":
    app.run(debug=True)
