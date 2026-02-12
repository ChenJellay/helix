"""GitHub Actions workflow parser — reads CI config from local repos.

Helix parses ``.github/workflows/*.yml`` from the local filesystem to
understand what CI checks are configured for a project.  This context is
fed to agents (Scope Checker, Gap Analyzer) so they can factor CI
coverage into their analysis.

Usage::

    from helix.integrations.workflow_parser import parse_workflows

    summary = parse_workflows("/absolute/path/to/repo")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def parse_workflows(repo_dir: str | Path) -> list[dict[str, Any]]:
    """Parse all GitHub Actions workflow files in a repository.

    Args:
        repo_dir: Absolute path to the repository root.

    Returns:
        A list of workflow summary dicts, each containing:
        - ``name``: Workflow display name.
        - ``file``: Relative path to the workflow file.
        - ``triggers``: List of event names that trigger this workflow.
        - ``jobs``: List of job summary dicts (name, steps count, runs-on).
        - ``path_filters``: Paths that trigger the workflow (if ``on.push.paths``
          or ``on.pull_request.paths`` are set).
    """
    workflows_dir = Path(repo_dir) / ".github" / "workflows"
    if not workflows_dir.is_dir():
        logger.debug("No .github/workflows directory in %s", repo_dir)
        return []

    results: list[dict[str, Any]] = []

    for yml_path in sorted(workflows_dir.glob("*.yml")):
        try:
            data = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            results.append(_summarise_workflow(yml_path, data, repo_dir))
        except Exception:
            logger.warning("Failed to parse workflow %s", yml_path, exc_info=True)

    # Also check .yaml extension
    for yml_path in sorted(workflows_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            results.append(_summarise_workflow(yml_path, data, repo_dir))
        except Exception:
            logger.warning("Failed to parse workflow %s", yml_path, exc_info=True)

    return results


def summarise_for_prompt(workflows: list[dict[str, Any]]) -> str:
    """Render workflow summaries as a compact text block for LLM prompts.

    Returns an empty string if there are no workflows.
    """
    if not workflows:
        return ""

    lines = ["CI/CD Workflows:"]
    for wf in workflows:
        lines.append(f"  - {wf['name']} ({wf['file']})")
        lines.append(f"    Triggers: {', '.join(wf['triggers']) or 'none'}")
        if wf["path_filters"]:
            lines.append(f"    Path filters: {', '.join(wf['path_filters'])}")
        for job in wf["jobs"]:
            lines.append(
                f"    Job: {job['name']} ({job['steps_count']} steps, "
                f"runs-on: {job['runs_on']})"
            )
    return "\n".join(lines)


# ── Internals ─────────────────────────────────────────────────────────


def _summarise_workflow(
    path: Path, data: dict, repo_dir: str | Path
) -> dict[str, Any]:
    """Extract a summary dict from a parsed workflow YAML."""
    name = data.get("name", path.stem)
    triggers = _extract_triggers(data.get("on", data.get(True, {})))
    path_filters = _extract_path_filters(data.get("on", data.get(True, {})))

    jobs: list[dict[str, Any]] = []
    for job_id, job_def in (data.get("jobs") or {}).items():
        if not isinstance(job_def, dict):
            continue
        steps = job_def.get("steps", [])
        jobs.append({
            "name": job_def.get("name", job_id),
            "steps_count": len(steps) if isinstance(steps, list) else 0,
            "runs_on": job_def.get("runs-on", "unknown"),
        })

    rel_path = str(Path(path).relative_to(Path(repo_dir)))

    return {
        "name": name,
        "file": rel_path,
        "triggers": triggers,
        "jobs": jobs,
        "path_filters": path_filters,
    }


def _extract_triggers(on_value: Any) -> list[str]:
    """Normalise the ``on:`` field into a list of event name strings."""
    if isinstance(on_value, str):
        return [on_value]
    if isinstance(on_value, list):
        return [str(t) for t in on_value]
    if isinstance(on_value, dict):
        return list(on_value.keys())
    return []


def _extract_path_filters(on_value: Any) -> list[str]:
    """Extract path filters from ``on.push.paths`` / ``on.pull_request.paths``."""
    if not isinstance(on_value, dict):
        return []

    paths: list[str] = []
    for event in ("push", "pull_request"):
        event_cfg = on_value.get(event, {})
        if isinstance(event_cfg, dict):
            paths.extend(event_cfg.get("paths", []))
    return paths
