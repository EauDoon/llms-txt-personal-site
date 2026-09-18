# Security Policy

This repository is a static site template intended for personal forks. The hosted default content contains no runtime server code and no third party integrations beyond the static asset boundary.

## Reporting a Vulnerability

Please report security issues through GitHub private vulnerability reporting.

1. Open the repository page on GitHub.
2. Go to the Security tab.
3. Click "Report a vulnerability".
4. Provide a clear description, reproduction steps, and impact assessment.

GitHub will route the report to the maintainers privately. Please do not file public issues for suspected vulnerabilities before a coordinated disclosure window has elapsed.

## Scope

In scope for the template itself:

- Unsafe HTML or scripting in the static site that could affect forkers.
- Dependency issues in build tooling that ship with the template.
- Misconfigured repository settings shipped with the template.

Out of scope for the template:

- Content added by individual forks.
- Hosting or CDN configuration chosen by a fork operator.
- Custom domains, third party analytics, or external services wired in by a fork.

## Response Expectations

The maintainers aim to acknowledge new reports within seven days. Fix timelines depend on severity and on whether the issue affects the template or only specific forks.

## Supported Versions

Only the latest commit on the default branch receives security fixes for the template. Older snapshots are not patched.
