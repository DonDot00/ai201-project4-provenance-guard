import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from audit_log import get_log, log_submission
from signals import get_llm_signal

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

    # Placeholders until Signal 2 and the real weighted formula (planning.md) are wired in.
    confidence = signal1["llm_score"]
    label = "Uncertain"

    log_submission(
        content_id=content_id,
        creator_id=creator_id,
        attribution=signal1["verdict"],
        confidence=confidence,
        signal1_score=signal1["llm_score"],
        status="processed",
    )

    return jsonify(
        {
            "content_id": content_id,
            "attribution": signal1,
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
