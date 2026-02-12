"""Helix CLI — local-first commands for scope checking and repo management.

Usage::

    # Check a branch against main
    python -m helix.cli check --repo . --base main --head feature/fraud

    # Check the current branch (auto-detect head)
    python -m helix.cli check --repo .

    # Link a local repo to a Helix project
    python -m helix.cli link --repo . --project-id <UUID>

    # Install a git pre-push hook
    python -m helix.cli install-hook --repo .
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap

import click

from helix.config import settings


@click.group()
def cli():
    """Helix — AI-native technical program management."""
    pass


# ── check ─────────────────────────────────────────────────────────────


@cli.command()
@click.option(
    "--repo",
    default=".",
    help="Path to the git repository (default: current directory).",
)
@click.option(
    "--base",
    default=None,
    help="Base branch to diff against (default: auto-detect main/master).",
)
@click.option(
    "--head",
    default=None,
    help="Head branch to check (default: currently checked-out branch).",
)
@click.option(
    "--sync",
    "run_sync",
    is_flag=True,
    default=False,
    help="Run synchronously and print the full report (skip background task).",
)
def check(repo: str, base: str | None, head: str | None, run_sync: bool):
    """Run a scope-creep check comparing two branches."""
    asyncio.run(_check(repo, base, head, run_sync))


async def _check(
    repo: str, base: str | None, head: str | None, run_sync: bool
) -> None:
    from helix.integrations.local_git import LocalGitClient
    from helix.integrations.path_resolver import repo_path_resolver

    # Resolve and validate the repo
    try:
        relative = repo_path_resolver.to_relative(repo)
    except ValueError:
        relative = repo

    try:
        abs_path = repo_path_resolver.resolve(relative)
    except ValueError as exc:
        click.secho(f"Error: {exc}", fg="red", err=True)
        sys.exit(1)

    git = LocalGitClient(abs_path)

    # Auto-detect branches
    if head is None:
        head = await git.current_branch()
    if base is None:
        base = await git.default_branch()

    if head == base:
        click.secho(
            f"Error: head branch ({head}) is the same as base ({base}).  "
            f"Checkout a feature branch first.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Helix scope check: {relative}  ({base}..{head})")

    if run_sync:
        # Run in-process (bypasses the API server)
        from helix.db.session import async_session_factory
        from helix.agents.scope_checker import ScopeCheckerAgent

        async with async_session_factory() as session:
            agent = ScopeCheckerAgent()
            result = await agent.check_branch(
                repo_path=relative,
                base_branch=base,
                head_branch=head,
                session=session,
            )
            await session.commit()

        if "error" in result:
            click.secho(f"Error: {result['error']}", fg="red", err=True)
            sys.exit(1)

        report = ScopeCheckerAgent._format_report(result)
        click.echo()
        click.echo(report)
    else:
        # Post to the local Helix API
        import httpx

        api_url = f"http://localhost:8000/api/check-local"
        payload = {
            "repo_path": relative,
            "base_branch": base,
            "head_branch": head,
        }
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": settings.helix_api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                click.echo(f"  Status: {data.get('status', 'unknown')}")
                click.echo(
                    f"  Check queued for {data.get('base_branch')}..{data.get('head_branch')}"
                )
                click.echo("  View results in the Helix dashboard or API.")
        except httpx.ConnectError:
            click.secho(
                "Error: Cannot reach the Helix API at localhost:8000.  "
                "Is the server running?  (Use --sync to run without the server.)",
                fg="red",
                err=True,
            )
            sys.exit(1)
        except httpx.HTTPStatusError as exc:
            click.secho(
                f"Error: API returned {exc.response.status_code}: "
                f"{exc.response.text}",
                fg="red",
                err=True,
            )
            sys.exit(1)


# ── link ──────────────────────────────────────────────────────────────


@cli.command()
@click.option(
    "--repo",
    default=".",
    help="Path to the git repository.",
)
@click.option(
    "--project-id",
    required=True,
    help="Helix project UUID to link this repo to.",
)
def link(repo: str, project_id: str):
    """Link a local repository to a Helix project."""
    asyncio.run(_link(repo, project_id))


async def _link(repo: str, project_id: str) -> None:
    from helix.integrations.path_resolver import repo_path_resolver

    try:
        relative = repo_path_resolver.to_relative(repo)
    except ValueError:
        relative = repo

    try:
        repo_path_resolver.resolve(relative)
    except ValueError as exc:
        click.secho(f"Error: {exc}", fg="red", err=True)
        sys.exit(1)

    import httpx

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": settings.helix_api_key,
    }
    payload = {"repo_path": relative}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"http://localhost:8000/api/projects/{project_id}",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            click.echo(
                f"Linked repo '{relative}' to project '{data.get('name')}' "
                f"({data.get('id')})"
            )
    except httpx.ConnectError:
        click.secho(
            "Error: Cannot reach the Helix API at localhost:8000.",
            fg="red",
            err=True,
        )
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        click.secho(
            f"Error: API returned {exc.response.status_code}: "
            f"{exc.response.text}",
            fg="red",
            err=True,
        )
        sys.exit(1)


# ── install-hook ──────────────────────────────────────────────────────


@cli.command("install-hook")
@click.option(
    "--repo",
    default=".",
    help="Path to the git repository.",
)
@click.option(
    "--hook",
    type=click.Choice(["pre-push", "post-commit"]),
    default="pre-push",
    help="Which git hook to install.",
)
def install_hook(repo: str, hook: str):
    """Install a git hook that triggers Helix scope checks automatically."""
    from pathlib import Path

    from helix.integrations.path_resolver import repo_path_resolver

    try:
        relative = repo_path_resolver.to_relative(repo)
    except ValueError:
        relative = repo

    try:
        abs_path = repo_path_resolver.resolve(relative)
    except ValueError as exc:
        click.secho(f"Error: {exc}", fg="red", err=True)
        sys.exit(1)

    hooks_dir = abs_path / ".git" / "hooks"
    hook_path = hooks_dir / hook

    if hook_path.exists():
        if not click.confirm(
            f"Hook {hook_path} already exists. Overwrite?", default=False
        ):
            click.echo("Aborted.")
            return

    hook_script = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # Helix scope-check hook — auto-generated by `helix install-hook`
        echo "Helix: triggering scope check..."
        python -m helix.cli check --repo "{abs_path}" &
    """)

    hook_path.write_text(hook_script)
    hook_path.chmod(0o755)
    click.echo(f"Installed {hook} hook at {hook_path}")


# ── Entry point ───────────────────────────────────────────────────────


def main():
    cli()


if __name__ == "__main__":
    main()
