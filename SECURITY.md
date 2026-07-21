# Security Policy

## Reporting a vulnerability

This project uses a self-hosted Tinode instance with AI NPCs for private use.

If you find a security issue:

- **Do not** open a public GitHub issue.
- Send a description to the repository owner via GitHub Issues with the `[security]` prefix.
- Or contact the maintainer directly through the repository's GitHub profile.

## Scope

- Tinode server itself — report upstream at https://github.com/tinode/chat
- AI NPC agent — API keys are local-only; no external attack surface
- Desktop clients — local-only, no remote code execution paths

## CI / supply chain

- All CI artifacts are built from source in GitHub Actions
- No pre-built binaries are published outside of GitHub Releases
- Dependencies are pinned via `package-lock.json` and `requirements.txt`