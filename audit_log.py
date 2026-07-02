import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.jsonl")


def log_submission(*, content_id, creator_id, attribution, confidence, llm_score, stylometric_score, label, status):
    entry = {
        "entry_type": "submission",
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylometric_score,
        "label": label,
        "status": status,
        "appeal_status": None,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def log_appeal(*, appeal_id, content_id, creator_reasoning, original_attribution, original_confidence, original_label):
    entry = {
        "entry_type": "appeal",
        "appeal_id": appeal_id,
        "content_id": content_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "creator_reasoning": creator_reasoning,
        "original_attribution": original_attribution,
        "original_confidence": original_confidence,
        "original_label": original_label,
        "appeal_status": "under_review",
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def find_submission(content_id):
    """Scans the log for the most recent submission entry matching content_id."""
    if not os.path.exists(LOG_PATH):
        return None
    match = None
    with open(LOG_PATH) as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("entry_type") == "submission" and entry.get("content_id") == content_id:
                match = entry
    return match


def get_log(limit=50):
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        lines = f.readlines()
    entries = [json.loads(line) for line in lines[-limit:]]
    entries.reverse()
    return entries
