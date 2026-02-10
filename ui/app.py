"""Helix Dashboard - Streamlit UI for the AI-Native TPgM Platform."""

import json

import httpx
import streamlit as st

# ── Configuration ─────────────────────────────────────────────────────────────

API_BASE = "http://helix-api:8000/api"
HEADERS = {"X-API-Key": "dev"}


def api_get(path: str, **kwargs) -> dict | list | None:
    """Make a GET request to the Helix API."""
    try:
        r = httpx.get(f"{API_BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(path: str, data: dict | None = None, **kwargs) -> dict | None:
    """Make a POST request to the Helix API."""
    try:
        r = httpx.post(f"{API_BASE}{path}", headers=HEADERS, json=data, timeout=60, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_patch(path: str, data: dict) -> dict | None:
    """Make a PATCH request to the Helix API."""
    try:
        r = httpx.patch(f"{API_BASE}{path}", headers=HEADERS, json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Helix TPM Dashboard",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar Navigation ───────────────────────────────────────────────────────

st.sidebar.title("🧬 Helix")
st.sidebar.caption("AI-Native TPM Platform")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    [
        "Projects",
        "Documents",
        "Risk Dashboard",
        "PR Activity",
        "Launch Checklist",
        "Gap Analysis",
    ],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.markdown(
    "Built on the philosophy of **Living State**: "
    "the Code updates the State, and the State constrains the Code."
)


# ── Projects Page ─────────────────────────────────────────────────────────────


def page_projects():
    st.title("Projects")
    st.markdown("Manage your technical programs and their linked repositories.")

    # Create new project
    with st.expander("Create New Project", expanded=False):
        with st.form("create_project"):
            name = st.text_input("Project Name", placeholder="My Feature Launch")
            description = st.text_area("Description", placeholder="Brief description...")
            github_repo = st.text_input(
                "GitHub Repository", placeholder="owner/repo (optional)"
            )
            submitted = st.form_submit_button("Create Project", type="primary")

            if submitted and name:
                result = api_post("/projects", {
                    "name": name,
                    "description": description,
                    "github_repo": github_repo or None,
                })
                if result:
                    st.success(f"Project '{name}' created!")
                    st.rerun()

    # List projects
    st.subheader("All Projects")
    data = api_get("/projects")
    if data and data.get("projects"):
        for proj in data["projects"]:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{proj['name']}**")
                    if proj.get("description"):
                        st.caption(proj["description"])
                with col2:
                    if proj.get("github_repo"):
                        st.code(proj["github_repo"], language=None)
                    st.caption(f"Created: {proj['created_at'][:10]}")
                with col3:
                    status_colors = {
                        "active": "🟢",
                        "launched": "🚀",
                        "archived": "📦",
                    }
                    icon = status_colors.get(proj["status"], "⚪")
                    st.markdown(f"{icon} **{proj['status'].title()}**")
    else:
        st.info("No projects yet. Create one above!")


# ── Documents Page ────────────────────────────────────────────────────────────


def page_documents():
    st.title("Documents")
    st.markdown("Upload PRDs, design docs, and meeting notes for AI analysis.")

    # Select project
    projects_data = api_get("/projects")
    if not projects_data or not projects_data.get("projects"):
        st.warning("Create a project first.")
        return

    project_names = {p["name"]: p["id"] for p in projects_data["projects"]}
    selected_project = st.selectbox("Select Project", list(project_names.keys()))
    project_id = project_names[selected_project]

    # Upload document
    with st.expander("Upload Document", expanded=False):
        with st.form("upload_doc"):
            title = st.text_input("Document Title")
            doc_type = st.selectbox(
                "Type", ["prd", "technical_design", "meeting_notes", "other"]
            )
            content = st.text_area("Content (Markdown)", height=300)
            submitted = st.form_submit_button("Upload & Analyze", type="primary")

            if submitted and title and content:
                result = api_post("/documents", {
                    "project_id": project_id,
                    "title": title,
                    "doc_type": doc_type,
                    "content": content,
                })
                if result:
                    st.success(
                        f"Document uploaded! Indexing and risk analysis running in background."
                    )
                    st.rerun()

    # List documents
    st.subheader(f"Documents for {selected_project}")
    docs = api_get(f"/projects/{project_id}/documents")
    if docs:
        for doc in docs:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{doc['title']}**")
                    st.caption(f"Type: {doc['doc_type']} | Created: {doc['created_at'][:10]}")
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

    projects_data = api_get("/projects")
    if not projects_data or not projects_data.get("projects"):
        st.warning("Create a project first.")
        return

    project_names = {p["name"]: p["id"] for p in projects_data["projects"]}
    selected_project = st.selectbox("Select Project", list(project_names.keys()))
    project_id = project_names[selected_project]

    risks = api_get(f"/projects/{project_id}/risks")
    if risks:
        for assessment in risks:
            st.subheader(f"Assessment: {assessment['created_at'][:10]}")

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
                    icon = impact_colors.get(impact, "⚪")
                    with st.container(border=True):
                        st.markdown(
                            f"{icon} **{risk.get('risk', 'Unknown')}** "
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

            st.divider()
    else:
        st.info("No risk assessments yet. Upload a PRD to trigger analysis.")


# ── PR Activity Page ──────────────────────────────────────────────────────────


def page_pr_activity():
    st.title("PR Activity")
    st.markdown("Scope-check results from GitHub pull request analysis.")

    projects_data = api_get("/projects")
    if not projects_data or not projects_data.get("projects"):
        st.warning("Create a project first.")
        return

    project_names = {p["name"]: p["id"] for p in projects_data["projects"]}
    selected_project = st.selectbox("Select Project", list(project_names.keys()))
    project_id = project_names[selected_project]

    checks = api_get(f"/projects/{project_id}/scope-checks")
    if checks:
        for check in checks:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(
                        f"**PR #{check['pr_number']}** in `{check['repo_name']}`"
                    )
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
            "No PR checks yet. Link a GitHub repo and configure the Helix webhook."
        )


# ── Launch Checklist Page ─────────────────────────────────────────────────────


def page_launch():
    st.title("Launch Checklist")
    st.markdown("AI-prefilled launch readiness checklists.")

    projects_data = api_get("/projects")
    if not projects_data or not projects_data.get("projects"):
        st.warning("Create a project first.")
        return

    project_names = {p["name"]: p["id"] for p in projects_data["projects"]}
    selected_project = st.selectbox("Select Project", list(project_names.keys()))
    project_id = project_names[selected_project]

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Generate Checklist", type="primary"):
            with st.spinner("AI is analyzing project artifacts..."):
                result = api_get(f"/launch/{project_id}/checklist?regenerate=true")
                if result:
                    st.success("Checklist generated!")
                    st.rerun()
    with col2:
        if st.button("Load Existing"):
            pass  # Just triggers a rerun to load

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
            st.subheader("Warnings")
            for w in warnings:
                st.warning(w)

        # Missing info
        missing = checklist.get("missing_information", [])
        if missing:
            st.subheader("Missing Information")
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
    st.markdown("Post-launch metric monitoring - the Promise Keeper.")

    projects_data = api_get("/projects")
    if not projects_data or not projects_data.get("projects"):
        st.warning("Create a project first.")
        return

    project_names = {p["name"]: p["id"] for p in projects_data["projects"]}
    selected_project = st.selectbox("Select Project", list(project_names.keys()))
    project_id = project_names[selected_project]

    if st.button("Run Gap Analysis Now", type="primary"):
        with st.spinner("Analyzing metrics against PRD promises..."):
            result = api_post(f"/analysis/{project_id}/gap")
            if result:
                st.success("Gap analysis complete!")
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
            st.subheader("Metric Gaps")
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
            st.subheader("Metrics On Track")
            for m in on_track:
                st.markdown(f"- ✅ {m}")

        if analysis.get("next_review_date"):
            st.caption(f"Next review: {analysis['next_review_date']}")
    else:
        st.info(
            "No gap analysis yet. Ensure metric targets are defined, "
            "then click 'Run Gap Analysis Now'."
        )


# ── Router ────────────────────────────────────────────────────────────────────

page_map = {
    "Projects": page_projects,
    "Documents": page_documents,
    "Risk Dashboard": page_risks,
    "PR Activity": page_pr_activity,
    "Launch Checklist": page_launch,
    "Gap Analysis": page_gap_analysis,
}

page_map[page]()
