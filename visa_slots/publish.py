"""Publish status.json as a single-commit orphan branch `status` (history never grows).

The page reads https://raw.githubusercontent.com/<repo>/status/status.json.
"""
import json
import logging
import os
import subprocess

log = logging.getLogger(__name__)
BRANCH = "status"


def _git(*args: str, input: bytes | None = None) -> str:
    return subprocess.run(["git", *args], input=input, capture_output=True, check=True).stdout.decode().strip()


def load() -> dict:
    """Last published state, so a new run carries on where the previous one stopped."""
    try:
        _git("fetch", "-q", "--depth=1", "origin", BRANCH)
        return json.loads(_git("show", f"FETCH_HEAD:status.json"))
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        log.warning("no previous state: %s", getattr(e, "stderr", e))
        return {}


def save(state: dict) -> None:
    if os.environ.get("DRY_RUN"):
        with open("status.json", "w") as f:
            json.dump(state, f, indent=1, ensure_ascii=False)
        return
    blob = _git("hash-object", "-w", "--stdin", input=json.dumps(state, indent=1, ensure_ascii=False).encode())
    tree = _git("mktree", input=f"100644 blob {blob}\tstatus.json\n".encode())
    commit = _git(
        "-c", "user.name=visa-slots", "-c", "user.email=visa-slots@users.noreply.github.com",
        "commit-tree", tree, "-m", f"status {state.get('updated_at', '')}",
    )
    _git("push", "-q", "-f", "origin", f"{commit}:refs/heads/{BRANCH}")
