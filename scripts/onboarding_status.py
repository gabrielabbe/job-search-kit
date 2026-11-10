"""Report whether this project has been set up for its candidate yet.

Run at the start of every session (a SessionStart hook in .claude/settings.json does it). Prints one short block that
tells Claude whether to run the onboarding interview or continue the normal workflow.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))


def bootstrap():
    """Create the candidate's private working files from templates/ the first time. Never overwrites anything."""
    import shutil
    made = []
    for src in sorted((ROOT / "templates" / "memory").glob("*.md")):
        dst = ROOT / ".claude" / "memory" / src.name
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            made.append(f".claude/memory/{src.name}")
    cfg = ROOT / "config" / "search-profiles.yaml"
    if not cfg.exists():
        shutil.copyfile(ROOT / "templates" / "search-profiles.yaml", cfg)
        made.append("config/search-profiles.yaml")
    for d in ("jobs/_archive", "jobs/_scans", "data/profile", "data/evidence", "reference/research", "linkedin", "portfolio", "resumes/generated"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    return made


def main():
    bootstrap()
    profile_md = ROOT / ".claude" / "memory" / "profile.md"
    status = "NOT_STARTED"
    if profile_md.exists():
        m = re.search(r"ONBOARDING_STATUS:\s*([A-Z_]+)", profile_md.read_text(encoding="utf-8"))
        if m:
            status = m.group(1)
    try:
        import profile_loader
        cfg_ok = profile_loader.is_onboarded()
    except Exception:
        cfg_ok = False
    ev = ROOT / "data" / "evidence" / "evidence.json"
    n_ev = len(json.loads(ev.read_text(encoding="utf-8")).get("records", [])) if ev.exists() else 0

    if status == "COMPLETE" and cfg_ok:
        print(f"[job-search-kit] Onboarded. {n_ev} evidence records. Continue the normal workflow in CLAUDE.md.")
        return
    print("[job-search-kit] ONBOARDING REQUIRED.")
    print(f"  profile.md status: {status}; search profile ready: {cfg_ok}; evidence records: {n_ev}.")
    if status == "IN_PROGRESS":
        print("  An interview is already under way: read .claude/memory/profile.md for what is recorded, then resume "
              "`.claude/skills/onboarding/SKILL.md` at the first round that is not marked done.")
    else:
        print("  Before anything else, greet the user, explain in two sentences what this project does, and start "
              "`.claude/skills/onboarding/SKILL.md`. Do this even if their first message is only a greeting or asks for "
              "something else: answer briefly, then start onboarding.")
    print("  Record every fact the user states as soon as they state it (evidence_tool.py and the memory files).")


if __name__ == "__main__":
    main()
