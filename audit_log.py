import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.jsonl")


def log_submission(*, content_id, creator_id, attribution, confidence, signal1_score, status):
    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
        "confidence": confidence,
        "signal1_score": signal1_score,
        "status": status,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def get_log(limit=50):
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        lines = f.readlines()
    entries = [json.loads(line) for line in lines[-limit:]]
    entries.reverse()
    return entries
