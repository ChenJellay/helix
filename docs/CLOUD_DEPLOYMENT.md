# Cloud Deployment (Future)

Cloud mode enables GitHub webhook and GitHub Action integration so Helix can watch repositories hosted on GitHub and post scope-check results directly on pull requests.

**Status:** Not yet implemented for the current MVP. The local-first deployment model is the default.

## When to use cloud mode

- Your team uses GitHub-hosted repositories and wants scope checks on every PR.
- Multiple developers need a shared, centralised Helix instance.
- You want automatic PR comments with violation reports.

## High-level architecture

```
PR opened/updated on GitHub
        |
        +---> GitHub Webhook ----> Helix API (/api/webhooks/github)
        |         (HMAC-SHA256)
        |
        +---> GitHub Action  ----> Helix API (/api/webhooks/github)
                  (API key)
                                        |
                                        v
                              ScopeCheckerAgent.check_pr()
                                  |-- fetch PR diff (GitHub API)
                                  |-- retrieve design doc (RAG)
                                  |-- LLM alignment check
                                  +-- post comment on PR
```

## Configuration

Set `HELIX_MODE=cloud` in your `.env` and provide:

```bash
HELIX_MODE=cloud
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_WEBHOOK_SECRET=your-webhook-secret
HELIX_API_KEY=your-api-key
```

The webhook and GitHub Action routes are only registered when `HELIX_MODE=cloud`.

## Implementation roadmap

- [ ] Webhook signature verification (code exists, needs production hardening)
- [ ] GitHub Action packaging and Marketplace publishing
- [ ] Multi-developer dashboard with team-wide scope check history
- [ ] GitHub App authentication (replaces personal access tokens)
- [ ] PR status checks (pass/fail) in addition to comments
