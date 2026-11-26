# Automated maintenance

Dependencies and security fixes are looked after without anyone watching. This page says what
runs, what is merged on its own and what always waits for a person.

## Renovate

Configuration: [`renovate.json`](../renovate.json).

- Updates are raised on weekday nights (00:00 to 06:00, Europe/Berlin), at most 5 PRs open at
  once. A release must be 3 days old first. Security fixes are raised at once and skip that wait.
- Python dependencies, dev tools and GitHub Actions are grouped.
- Renovate merges a PR itself once every check on it is green.
- **Merged on their own:** patch and minor updates, pins and digests, and security fixes of
  packages that are not listed below.
- **Never merged on their own** (label `needs-review`):
  - every major update (label `major`);
  - minor updates of `0.x` packages;
  - the Python and uv versions;
  - core libraries: numpy, soundfile, demucs, torch, torchaudio, PySide6, sounddevice,
    PyInstaller;
  - the release chain actions `pypa/gh-action-pypi-publish`, `actions/upload-artifact`,
    `actions/download-artifact`;
  - lock file maintenance (Monday night), see the deviations below.

## Vulnerability scan

[`vulnerability-scan.yml`](../.github/workflows/vulnerability-scan.yml) runs `pip-audit` on
`uv.lock` every Sunday night. One open issue labelled `vulnerability` lists the findings; a
clean run closes it. It is not a required check.

## Weekly Claude task

Every Monday morning a scheduled Claude task in the cloud (`Softwarepflege soloslot`):

1. Looks at open PRs by `renovate[bot]`, at open issues labelled `vulnerability` or
   `security-release`, and at security fixes that are merged but not released. If there is
   nothing, it ends at once.
2. Repairs red checks on those PRs.
3. Merges non-major updates after an independent review and green CI.
4. Prepares major updates, but does not merge them, and lists them in its report.
5. Decides on a security release, see below.

It touches no other PRs, never force-pushes and changes no settings. CI can be started by hand
with the `workflow_dispatch` trigger of `ci.yml`.

## Security releases

When pull requests labelled `security` were merged after the latest release, the weekly task
decides whether to publish them:

- It releases only when the fixed dependency is part of the published package or the
  installers (not a dev, test or CI tool), and when everything on `main` since the latest
  release is dependency updates, maintenance and bug fixes.
- It opens a pull request `Security release vX.Y.Z` that raises the patch version in
  `pyproject.toml`, refreshes `uv.lock` and moves the changelog entries from "Unreleased" to
  the new version, and merges it after an independent review and green CI. If
  `pyproject.toml` already holds a version that has no tag yet, that version is released and
  not raised again.
- It then creates the tag `vX.Y.Z` on that merge commit. The tag starts
  [`release.yml`](../.github/workflows/release.yml), which publishes to PyPI, builds the
  installers and writes the GitHub release.
- It checks afterwards that the release is published.
- In any other case, or when in doubt, it publishes nothing and opens an issue
  `Security release needs a decision` (label `security-release`).

At most one security release per run. Every other release stays a decision of the maintainer.

## Deviations from the standard

- Lock file maintenance is not merged on its own: the tests do not cover audio and GUI
  behaviour, so a refresh of every transitive dependency gets a review.
- The security release is started by a tag that the weekly task creates, not by a
  `workflow_dispatch` run: `release.yml` only reacts to a pushed tag and stays as it is.
