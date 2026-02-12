"""Helix Dashboard - Streamlit UI for the AI-Native TPgM Platform.

A non-technical user should be able to manage projects, link repos,
upload documents, and run every analysis command from this dashboard.
"""

from __future__ import annotations

import httpx
import streamlit as st

# ── Configuration ─────────────────────────────────────────────────────────────

API_BASE = "http://helix-api:8000/api"
HEALTH_URL = "http://helix-api:8000/health"
HEADERS = {"X-API-Key": "dev"}


# ── API Helpers ───────────────────────────────────────────────────────────────


def _friendly_error(exc: Exception) -> str:
    """Return a short user-friendly error message."""
    msg = str(exc)
    if "Connection refused" in msg or "ConnectError" in msg:
        return "Cannot reach the Helix API server. Is it running?"
    if "timed out" in msg.lower() or "timeout" in msg.lower():
        return "The request timed out. The server may be busy — try again shortly."
    if "404" in msg:
        return "The requested resource was not found (404)."
    if "400" in msg:
        # Try to extract the detail from the response body
        try:
            detail = exc.response.json().get("detail", msg)  # type: ignore[union-attr]
            return f"Bad request: {detail}"
        except Exception:
            return f"Bad request: {msg}"
    return f"API error: {msg}"


def api_get(path: str, **kwargs) -> dict | list | None:
    """GET request to the Helix API."""
    try:
        r = httpx.get(f"{API_BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(_friendly_error(e))
        return None


def api_post(path: str, data: dict | None = None, **kwargs) -> dict | None:
    """POST request to the Helix API."""
    try:
        r = httpx.post(
            f"{API_BASE}{path}", headers=HEADERS, json=data, timeout=120, **kwargs
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(_friendly_error(e))
        return None


def api_patch(path: str, data: dict) -> dict | None:
    """PATCH request to the Helix API."""
    try:
        r = httpx.patch(
            f"{API_BASE}{path}", headers=HEADERS, json=data, timeout=30
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(_friendly_error(e))
        return None


def api_delete(path: str) -> bool:
    """DELETE request to the Helix API. Returns True on success."""
    try:
        r = httpx.delete(f"{API_BASE}{path}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        return True
    except Exception as e:
        st.error(_friendly_error(e))
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_projects() -> list[dict]:
    """Fetch the full project list (cached per run)."""
    if "projects_cache" not in st.session_state:
        data = api_get("/projects")
        st.session_state.projects_cache = (
            data.get("projects", []) if data else []
        )
    return st.session_state.projects_cache


def _selected_project() -> dict | None:
    """Return the currently-selected project dict, or None."""
    return st.session_state.get("selected_project")


def _selected_project_id() -> str | None:
    proj = _selected_project()
    return proj["id"] if proj else None


# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Helix TPM Dashboard",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("🧬 Helix")
st.sidebar.caption("AI-Native TPM Platform")

# Health indicator
try:
    health = httpx.get(HEALTH_URL, timeout=3).json()
    st.sidebar.success(f"API connected  (v{health.get('version', '?')})", icon="✅")
except Exception:
    st.sidebar.error("API unreachable", icon="🔴")

st.sidebar.divider()

# Navigation
page = st.sidebar.radio(
    "Navigate",
    [
        "Projects",
        "Documents",
        "Risk Dashboard",
        "Scope Checks",
        "Launch Checklist",
        "Gap Analysis",
    ],
    label_visibility="collapsed",
)

# Global project selector (available on all pages except Projects)
st.sidebar.divider()
projects_list = _load_projects()

if projects_list:
    project_names = [p["name"] for p in projects_list]
    # Preserve selection across page switches
    prev_idx = 0
    if "selected_project" in st.session_state:
        prev_name = st.session_state["selected_project"]["name"]
        if prev_name in project_names:
            prev_idx = project_names.index(prev_name)

    chosen_name = st.sidebar.selectbox(
        "Active Project",
        project_names,
        index=prev_idx,
        help="Select the project to work with across all pages.",
    )
    # Store the full dict
    st.session_state.selected_project = next(
        p for p in projects_list if p["name"] == chosen_name
    )
else:
    st.sidebar.info("No projects yet — create one on the Projects page.")
    st.session_state.pop("selected_project", None)

st.sidebar.divider()
st.sidebar.markdown(
    "Built on the philosophy of **Living State**: "
    "the Code updates the State, and the State constrains the Code."
)


# ── Projects Page ─────────────────────────────────────────────────────────────


def page_projects():
    st.title("Projects")
    st.markdown("Manage your technical programs and their linked repositories.")

    # ── Getting Started banner ────────────────────────────────────────
    if not projects_list:
        st.info(
            "**Getting Started**  \n"
            "1. **Create a project** below  \n"
            "2. **Link a repository** from your workspace  \n"
            "3. **Upload a PRD** on the Documents page  \n"
            "4. **Run analysis** — risk, scope check, gap analysis — all from the dashboard",
            icon="👋",
        )

    # ── Create new project ────────────────────────────────────────────
    with st.expander("➕ Create New Project", expanded=not bool(projects_list)):
        # Fetch workspace repos for the dropdown
        workspace_data = api_get("/workspace/repos")
        repo_choices: list[str] = []
        if workspace_data and workspace_data.get("repos"):
            repo_choices = [r["path"] for r in workspace_data["repos"]]

        with st.form("create_project"):
            name = st.text_input("Project Name", placeholder="My Feature Launch")
            description = st.text_area(
                "Description", placeholder="Brief description of the project..."
            )

            st.markdown("**Link a Repository** *(optional)*")
            col_repo1, col_repo2 = st.columns([1, 1])
            with col_repo1:
                repo_dropdown = st.selectbox(
                    "Select from workspace",
                    ["(none)"] + repo_choices,
                    help="Git repositories discovered in your HELIX_WORKSPACE.",
                )
            with col_repo2:
                repo_manual = st.text_input(
                    "Or enter path manually",
                    placeholder="relative/path/to/repo",
                    help="Relative to HELIX_WORKSPACE, or an absolute path.",
                )

            github_repo = st.text_input(
                "GitHub Repository *(cloud mode)*",
                placeholder="owner/repo (optional)",
            )

            submitted = st.form_submit_button("Create Project", type="primary")

            if submitted and name:
                repo_path = (
                    repo_manual.strip()
                    if repo_manual.strip()
                    else (repo_dropdown if repo_dropdown != "(none)" else None)
                )
                with st.spinner("Creating project..."):
                    result = api_post(
                        "/projects",
                        {
                            "name": name,
                            "description": description,
                            "repo_path": repo_path or None,
                            "github_repo": github_repo or None,
                        },
                    )
                if result:
                    st.toast(f"Project '{name}' created!", icon="✅")
                    st.session_state.pop("projects_cache", None)
                    st.rerun()

    # ── List projects ─────────────────────────────────────────────────
    st.subheader("All Projects")
    if projects_list:
        for proj in projects_list:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{proj['name']}**")
                    if proj.get("description"):
                        st.caption(proj["description"])
                with col2:
                    if proj.get("repo_path"):
                        st.markdown(f"📂 `{proj['repo_path']}`")
                    elif proj.get("github_repo"):
                        st.markdown(f"🐙 `{proj['github_repo']}`")
                    else:
                        st.caption("No repository linked")
                    st.caption(f"Created: {proj['created_at'][:10]}")
                with col3:
                    status_colors = {
                        "active": "🟢",
                        "launched": "🚀",
                        "archived": "📦",
                    }
                    icon = status_colors.get(proj["status"], "⚪")
                    st.markdown(f"{icon} **{proj['status'].title()}**")

                # Link repo button for projects without a repo
                if not proj.get("repo_path"):
                    with st.expander("🔗 Link Repository"):
                        ws = api_get("/workspace/repos")
                        choices = (
                            [r["path"] for r in ws["repos"]] if ws and ws.get("repos") else []
                        )
                        key_prefix = f"link_{proj['id']}"
                        col_a, col_b = st.columns([2, 1])
                        with col_a:
                            if choices:
                                link_repo = st.selectbox(
                                    "Repository",
                                    choices,
                                    key=f"{key_prefix}_sel",
                                )
                            else:
                                link_repo = st.text_input(
                                    "Repository path",
                                    key=f"{key_prefix}_txt",
                                    placeholder="relative/path",
                                )
                        with col_b:
                            if st.button("Link", key=f"{key_prefix}_btn", type="primary"):
                                if link_repo:
                                    with st.spinner("Linking..."):
                                        res = api_patch(
                                            f"/projects/{proj['id']}",
                                            {"repo_path": link_repo},
                                        )
                                    if res:
                                        st.toast("Repository linked!", icon="🔗")
                                        st.session_state.pop("projects_cache", None)
                                        st.rerun()
                                else:
                                    st.warning("Select or enter a repo path first.")
    else:
        st.info("No projects yet. Create one above!")


# ── Documents Page ────────────────────────────────────────────────────────────


def page_documents():
    st.title("Documents")
    st.markdown("Upload PRDs, design docs, and meeting notes for AI analysis.")

    proj = _selected_project()
    if not proj:
        st.warning("Select or create a project first (see sidebar).")
        return
    project_id = proj["id"]

    # Upload document
    with st.expander("📄 Upload Document", expanded=False):
        with st.form("upload_doc"):
            title = st.text_input("Document Title")
            doc_type = st.selectbox(
                "Type", ["prd", "technical_design", "meeting_notes", "other"]
            )
            content = st.text_area("Content (Markdown)", height=300)
            submitted = st.form_submit_button("Upload & Analyze", type="primary")

            if submitted and title and content:
                with st.spinner("Uploading and indexing..."):
                    result = api_post(
                        "/documents",
                        {
                            "project_id": project_id,
                            "title": title,
                            "doc_type": doc_type,
                            "content": content,
                        },
                    )
                if result:
                    st.toast(
                        "Document uploaded! Indexing & risk analysis running in background.",
                        icon="📄",
                    )
                    st.rerun()

    # List documents
    st.subheader(f"Documents for {proj['name']}")
    docs = api_get(f"/projects/{project_id}/documents")
    if docs:
        for doc in docs:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{doc['title']}**")
                    st.caption(
                        f"Type: {doc['doc_type']} | Created: {doc['created_at'][:10]}"
                    )
                with col2:
                    index_status = doc.get("indexed", "pending")
                    status_icons = {
                        "indexed": "✅ Indexed",
                        "processing": "⏳ Processing",
                        "pending": "🕐 Pending",
                        "failed": "❌ Failed",
                    }
                    st.markdown(status_icons.get(index_status, index_status))
                with st.expander("View Content"):
                    st.markdown(doc["content"][:2000])
    else:
        st.info("No documents uploaded yet.")


# ── Risk Dashboard ────────────────────────────────────────────────────────────


def page_risks():
    st.title("Risk Dashboard")
    st.markdown("AI-generated risk assessments from your PRDs and design documents.")

    proj = _selected_project()
    if not proj:
        st.warning("Select or create a project first (see sidebar).")
        return
    project_id = proj["id"]

    # ── Trigger risk analysis per document ────────────────────────────
    docs = api_get(f"/projects/{project_id}/documents")
    if docs:
        st.subheader("Analyze Documents")
        st.caption("Click to run (or re-run) AI risk analysis on any document.")
        for doc in docs:
            col_d, col_btn = st.columns([4, 1])
            with col_d:
                doc_label = doc["doc_type"].upper()
                st.markdown(f"**{doc['title']}** ({doc_label})")
            with col_btn:
                if st.button(
                    "Run Risk Analysis",
                    key=f"risk_{doc['id']}",
                    type="secondary",
                ):
                    with st.spinner(f"Analyzing {doc['title']}..."):
                        result = api_post(f"/analysis/risk/{doc['id']}")
                    if result:
                        st.toast("Risk analysis complete!", icon="🔍")
                        st.rerun()
        st.divider()

    # ── Display risk assessments ──────────────────────────────────────
    st.subheader("Risk Assessments")
    risks = api_get(f"/projects/{project_id}/risks")
    if risks:
        for assessment in risks:
            with st.container(border=True):
                st.markdown(f"**Assessment — {assessment['created_at'][:10]}**")

                # Overall score
                score = assessment.get("overall_score", 0)
                score_color = "🟢" if score < 0.3 else "🟡" if score < 0.6 else "🔴"
                st.metric("Overall Risk Score", f"{score_color} {score:.2f}")

                # Summary
                if assessment.get("summary"):
                    st.markdown(f"**Summary:** {assessment['summary']}")

                # Individual risks
                risk_items = assessment.get("risks", [])
                if risk_items:
                    st.markdown("#### Identified Risks")
                    for risk in risk_items:
                        impact = risk.get("impact", "medium")
                        impact_colors = {
                            "critical": "🔴",
                            "high": "🟠",
                            "medium": "🟡",
                            "low": "🟢",
                        }
                        risk_icon = impact_colors.get(impact, "⚪")
                        with st.container(border=True):
                            st.markdown(
                                f"{risk_icon} **{risk.get('risk', 'Unknown')}** "
                                f"(p={risk.get('probability', 0):.0%}, "
                                f"team: {risk.get('blocking_team', 'N/A')})"
                            )
                            if risk.get("mitigation"):
                                st.caption(f"Mitigation: {risk['mitigation']}")

                # Dependencies
                deps = assessment.get("dependencies", [])
                if deps:
                    st.markdown("#### Dependencies")
                    for dep in deps:
                        st.markdown(
                            f"- **{dep.get('target', '')}** "
                            f"({dep.get('type', 'hard')}): {dep.get('description', '')}"
                        )
    else:
        if docs:
            st.info(
                "No risk assessments yet. Use the buttons above to analyze your documents."
            )
        else:
            st.info(
                "No risk assessments yet. Upload a PRD on the Documents page to get started."
            )


# ── Scope Checks Page ────────────────────────────────────────────────────────


def page_scope_checks():
    st.title("Scope Checks")
    st.markdown(
        "Compare feature branches against design documents to detect scope creep."
    )

    proj = _selected_project()
    if not proj:
        st.warning("Select or create a project first (see sidebar).")
        return
    project_id = proj["id"]
    repo_path = proj.get("repo_path")

    # ── Run Scope Check form ──────────────────────────────────────────
    st.subheader("Run Scope Check")

    if not repo_path:
        st.warning(
            "This project has no linked repository. "
            "Go to the **Projects** page to link one first."
        )
    else:
        st.markdown(f"Repository: `{repo_path}`")

        # Fetch branches
        branch_data = api_get(f"/workspace/repos/{repo_path}/branches")
        if branch_data:
            branches = branch_data.get("branches", [])
            current_branch = branch_data.get("current_branch", "")
            default_branch = branch_data.get("default_branch", "main")

            if not branches:
                st.warning("No branches found in this repository.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    default_idx = (
                        branches.index(default_branch)
                        if default_branch in branches
                        else 0
                    )
                    base = st.selectbox(
                        "Base Branch (compare against)",
                        branches,
                        index=default_idx,
                        help="Typically main or master.",
                    )
                with col2:
                    current_idx = (
                        branches.index(current_branch)
                        if current_branch in branches
                        else 0
                    )
                    head = st.selectbox(
                        "Head Branch (to check)",
                        branches,
                        index=current_idx,
                        help="The feature branch to analyze.",
                    )

                if base == head:
                    st.warning("Base and head branches are the same — select a different feature branch.")
                else:
                    if st.button("🔍 Run Scope Check", type="primary"):
                        with st.spinner(
                            f"Running scope check: `{base}` → `{head}` ..."
                        ):
                            result = api_post(
                                "/check-local",
                                {
                                    "repo_path": repo_path,
                                    "base_branch": base,
                                    "head_branch": head,
                                },
                            )
                        if result:
                            st.toast(
                                "Scope check queued! Results will appear below shortly.",
                                icon="🔍",
                            )
                            # Brief pause then refresh to pick up results
                            import time

                            time.sleep(2)
                            st.rerun()

    # ── Historical scope check results ────────────────────────────────
    st.divider()
    st.subheader("Scope Check History")

    checks = api_get(f"/projects/{project_id}/scope-checks")
    if checks:
        for check in checks:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    # Show branch info for local checks, PR info for cloud
                    if check.get("base_branch") and check.get("head_branch"):
                        st.markdown(
                            f"**`{check['base_branch']}` → `{check['head_branch']}`**"
                        )
                    elif check.get("pr_number"):
                        st.markdown(
                            f"**PR #{check['pr_number']}** in `{check.get('repo_name', '?')}`"
                        )
                    else:
                        st.markdown("**Scope Check**")
                    st.caption(f"Checked: {check['created_at'][:16]}")
                with col2:
                    score = check.get("alignment_score", 1.0)
                    st.metric("Alignment", f"{score:.0%}")
                with col3:
                    if check.get("requires_tpm_approval") == "yes":
                        st.error("TPM Approval Required")
                    else:
                        st.success("OK")

                violations = check.get("violations", [])
                if violations:
                    with st.expander(f"{len(violations)} violation(s) found"):
                        for v in violations:
                            severity_icon = {
                                "critical": "🔴",
                                "warning": "🟡",
                                "info": "🔵",
                            }.get(v.get("severity", ""), "⚪")
                            st.markdown(
                                f"- {severity_icon} `{v.get('file', '')}`: "
                                f"{v.get('description', '')}"
                            )

                if check.get("summary"):
                    st.caption(check["summary"])
    else:
        st.info(
            "No scope checks yet. Link a repository and run a check above."
        )


# ── Launch Checklist Page ─────────────────────────────────────────────────────


def page_launch():
    st.title("Launch Checklist")
    st.markdown("AI-prefilled launch readiness checklists.")

    proj = _selected_project()
    if not proj:
        st.warning("Select or create a project first (see sidebar).")
        return
    project_id = proj["id"]

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🚀 Generate Checklist", type="primary"):
            with st.spinner("AI is analyzing project artifacts..."):
                result = api_get(f"/launch/{project_id}/checklist?regenerate=true")
            if result:
                st.toast("Checklist generated!", icon="🚀")
                st.rerun()
    with col2:
        if st.button("🔄 Refresh"):
            st.rerun()

    checklist = api_get(f"/launch/{project_id}/checklist")
    if checklist:
        st.subheader("Checklist Fields")

        fields = checklist.get("fields", [])
        for field in fields:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{field.get('field_name', 'Unknown')}**")
                    st.markdown(field.get("value", "N/A"))
                    if field.get("evidence"):
                        st.caption(f"Evidence: {field['evidence']}")
                with col2:
                    confidence = field.get("confidence", 0)
                    st.metric("Confidence", f"{confidence:.0%}")
                    if field.get("needs_human_review"):
                        st.warning("Needs Review")

        # Warnings
        warnings = checklist.get("warnings", [])
        if warnings:
            st.subheader("⚠️ Warnings")
            for w in warnings:
                st.warning(w)

        # Missing info
        missing = checklist.get("missing_information", [])
        if missing:
            st.subheader("❓ Missing Information")
            for m in missing:
                st.info(m)

        # Status
        st.divider()
        st.markdown(f"**Status:** {checklist.get('status', 'draft').title()}")
    else:
        st.info("No checklist yet. Click 'Generate Checklist' to create one.")


# ── Gap Analysis Page ─────────────────────────────────────────────────────────


def page_gap_analysis():
    st.title("Gap Analysis")
    st.markdown("Post-launch metric monitoring — the **Promise Keeper**.")

    proj = _selected_project()
    if not proj:
        st.warning("Select or create a project first (see sidebar).")
        return
    project_id = proj["id"]

    # ── Metric Targets CRUD ───────────────────────────────────────────
    st.subheader("Metric Targets")
    st.caption(
        "Define the metrics you promised in your PRD. "
        "Gap analysis compares actual values against these targets."
    )

    targets = api_get(f"/projects/{project_id}/metric-targets")
    targets = targets if targets else []

    # Show existing targets
    if targets:
        for t in targets:
            col_n, col_v, col_u, col_del = st.columns([3, 2, 1, 1])
            with col_n:
                st.markdown(f"**{t['metric_name']}**")
            with col_v:
                actual = t.get("actual_value") or "—"
                st.markdown(f"Target: `{t['target_value']}` | Actual: `{actual}`")
            with col_u:
                st.caption(t.get("unit", ""))
            with col_del:
                if st.button("🗑️", key=f"del_mt_{t['id']}"):
                    if api_delete(f"/metric-targets/{t['id']}"):
                        st.toast("Metric target removed.", icon="🗑️")
                        st.rerun()
    else:
        st.info(
            "No metric targets defined yet. "
            "Add at least one target below before running gap analysis."
        )

    # Add new target
    with st.expander("➕ Add Metric Target"):
        with st.form("add_metric_target"):
            mt_col1, mt_col2, mt_col3 = st.columns([2, 2, 1])
            with mt_col1:
                metric_name = st.text_input(
                    "Metric Name", placeholder="e.g. P95 Latency"
                )
            with mt_col2:
                target_value = st.text_input(
                    "Target Value", placeholder="e.g. < 200ms"
                )
            with mt_col3:
                unit = st.text_input("Unit", placeholder="ms")

            if st.form_submit_button("Add Target", type="primary"):
                if metric_name and target_value:
                    with st.spinner("Adding metric target..."):
                        result = api_post(
                            f"/projects/{project_id}/metric-targets",
                            {
                                "project_id": project_id,
                                "metric_name": metric_name,
                                "target_value": target_value,
                                "unit": unit,
                            },
                        )
                    if result:
                        st.toast("Metric target added!", icon="🎯")
                        st.rerun()
                else:
                    st.warning("Both metric name and target value are required.")

    # ── Run Gap Analysis ──────────────────────────────────────────────
    st.divider()
    st.subheader("Analysis Results")

    if st.button("📊 Run Gap Analysis Now", type="primary"):
        if not targets:
            st.warning(
                "Please add at least one metric target above "
                "before running gap analysis."
            )
        else:
            with st.spinner("Analyzing metrics against PRD promises..."):
                result = api_post(f"/analysis/{project_id}/gap")
            if result:
                st.toast("Gap analysis complete!", icon="📊")
                st.rerun()

    analysis = api_get(f"/analysis/{project_id}/gap")
    if analysis:
        # Overall status
        status = analysis.get("overall_status", "unknown")
        status_display = {
            "on_track": ("🟢", "On Track"),
            "at_risk": ("🟡", "At Risk"),
            "off_track": ("🔴", "Off Track"),
        }
        icon, label = status_display.get(status, ("⚪", status.title()))
        st.metric("Overall Status", f"{icon} {label}")

        # Executive summary
        if analysis.get("executive_summary"):
            st.markdown(f"**Summary:** {analysis['executive_summary']}")

        # Gaps
        gaps = analysis.get("gaps", [])
        if gaps:
            st.markdown("#### Metric Gaps")
            for gap in gaps:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"**{gap.get('metric_name', 'Unknown')}**")
                        st.markdown(
                            f"Target: {gap.get('target', 'N/A')} | "
                            f"Actual: {gap.get('actual', 'N/A')}"
                        )
                    with col2:
                        gap_pct = gap.get("gap_percentage", 0)
                        st.metric("Gap", f"{gap_pct:.1f}%")
                    with col3:
                        st.markdown(f"Priority: **{gap.get('priority', 'N/A')}**")
                        st.caption(f"Effort: {gap.get('effort_estimate', 'N/A')}")

                    if gap.get("root_causes"):
                        st.markdown("**Root Causes:**")
                        for cause in gap["root_causes"]:
                            st.markdown(f"- {cause}")
                    if gap.get("recommendations"):
                        st.markdown("**Recommendations:**")
                        for rec in gap["recommendations"]:
                            st.markdown(f"- {rec}")

        # Metrics on track
        on_track = analysis.get("metrics_on_track", [])
        if on_track:
            st.markdown("#### Metrics On Track")
            for m in on_track:
                st.markdown(f"- ✅ {m}")

        if analysis.get("next_review_date"):
            st.caption(f"Next review: {analysis['next_review_date']}")
    else:
        if targets:
            st.info("No gap analysis results yet. Click 'Run Gap Analysis Now' above.")
        else:
            st.info(
                "Add metric targets above, then run gap analysis to compare "
                "actual values against your PRD promises."
            )


# ── Router ────────────────────────────────────────────────────────────────────

page_map = {
    "Projects": page_projects,
    "Documents": page_documents,
    "Risk Dashboard": page_risks,
    "Scope Checks": page_scope_checks,
    "Launch Checklist": page_launch,
    "Gap Analysis": page_gap_analysis,
}

page_map[page]()
