# Automated maintenance

- **Renovate** (`renovate.json`) opens grouped update PRs on weekday nights (01:00-05:00,
  Europe/Berlin), at most 5 open at a time. Security updates are created immediately. Updates
  must be 3 days old before a normal PR is opened.
- **Automerge**: non-major updates are merged by GitHub once all required checks are green.
  Not automerged and labelled `needs-review`: major updates, 0.x minor updates, the Python and
  uv versions, the core libraries (numpy, soundfile, demucs/torch, PySide6, sounddevice,
  PyInstaller), the PyPI publish action and monthly lock file maintenance.
- **Security scan** (`security-scan.yml`): Sunday night, runs `pip-audit` on `uv.lock` and
  opens an issue labelled `security` on findings. It is not a required check.
- **Release check** (`release-check.yml`): Monday, opens an issue when security fixes were merged
  since the last release. Tags are pushed by a maintainer; `release.yml` then publishes.
- **Weekly maintenance run**: a scheduled Claude session handles open update PRs and issues.
