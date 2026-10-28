# Security Policy

## Supported versions

Security fixes land on the latest `vX.Y.Z-lite` release and on `main`. Older
minor versions are not maintained; upgrade to the latest tag.

| Version | Supported |
|---|---|
| Latest `vX.Y.Z-lite` | Yes |
| `main` | Yes, for unreleased fixes |
| Older releases | No |

## Reporting a vulnerability

**Do not open a public issue, pull request or OpenSpec change for a
vulnerability.** Public artifacts disclose the problem before a fix exists.

Report privately through one of these channels:

1. **GitHub Security Advisories** — open the repository's **Security** tab and
   choose **Report a vulnerability**. This is the preferred channel.
2. **Direct contact** — send a private message to [@jwackito](https://github.com/jwackito)
   on GitHub if advisories are unavailable.

Include:

- Affected version or commit.
- Deployment shape (Docker Compose, reverse proxy, provider).
- A reproduction or proof of concept, with secrets redacted.
- Impact: what an attacker gains and what they need first.

## What to expect

- Acknowledgement within 72 hours.
- An initial assessment and severity within 7 days.
- A coordinated disclosure date once a fix is ready. We will credit you unless
  you ask otherwise.
- We may ask you to test a candidate fix in a private fork.

## In scope

- Escapes from the Pydantic schema sandbox (`app/schema_sandbox.py`).
- Authentication or session bypass, including API tokens.
- Cross-user access to documents, jobs, batches, schemas or WebSockets.
- Leakage of provider secrets, `APP_SECRET_KEY`, `JWT_SECRET` or stored keys.
- Upload and parser issues: path traversal, arbitrary file write, command
  execution, or server-side request forgery through document handling.
- Privilege escalation between user and admin roles.
- Remote code execution or SQL injection reachable without credentials.

## Out of scope

- Vulnerabilities in Ollama, OpenAI, Gemini or the host operating system.
- Denial of service caused by intentionally expensive models or prompts.
- Findings that require an already-compromised host or database.
- Missing hardening headers with no demonstrated impact.
- Self-XSS and social-engineering scenarios.

## Safe harbour

We will not pursue legal action for good-faith research that follows this policy,
stays within your own deployment, avoids privacy violations and data
destruction, and gives us reasonable time to fix the issue before disclosure.

## Security fixes and the contribution workflow

Security work is the one documented exception to the rule that every pull
request carries a public OpenSpec change. Author the change in the private
advisory fork, land it with the fix, and disclose the change after the advisory
is published. Maintainers may bypass the public change guard for that merge.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the normal workflow.
