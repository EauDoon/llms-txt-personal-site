# Security Policy

This repository is a static site template intended for personal forks. The generated site contains no runtime server code and no third party integrations. The build and check scripts use only the Python standard library.

## Reporting a Vulnerability

Please report security issues through GitHub private vulnerability reporting.

1. Open the repository page on GitHub.
2. Go to the Security tab.
3. Click "Report a vulnerability".
4. Provide a clear description, reproduction steps, and impact assessment.

GitHub will route the report to the maintainers privately. Please do not file public issues for suspected vulnerabilities before a coordinated disclosure window has elapsed.

If the Security tab does not offer "Report a vulnerability", open a public issue titled "Security contact request" that contains no details of the problem. A maintainer will reply with a private way to send the report.

## Scope

In scope for the template itself:

- Unsafe HTML or scripting in the generated pages or the browser search that could affect forkers.
- The security headers shipped in `template/.htaccess`, `template/_headers`, and `template/vercel.json`: the Content-Security-Policy, `X-Frame-Options`, `Permissions-Policy`, `nosniff`, and the CORS header on the optional Agent Card.
- Path handling in the build, regeneration, and check scripts, such as following links out of the template or writing outside the output directory.
- The quality gate printing a configured forbidden string.
- Misconfigured repository settings shipped with the template.

Out of scope for the template:

- Content added by individual forks.
- Hosting or CDN configuration chosen by a fork operator.
- Custom domains, third party analytics, or external services wired in by a fork.

## Response Expectations

The maintainers aim to acknowledge new reports within seven days. Fix timelines depend on severity and on whether the issue affects the template or only specific forks.

## Supported Versions

Security fixes go to the default branch and ship in the next release of the latest major version, currently 1.x. Older releases and snapshots are not patched; upgrade to the latest 1.x release. `python scripts/version.py` prints the version you are running, and a built site's `content-manifest.json` names the release that generated it.
