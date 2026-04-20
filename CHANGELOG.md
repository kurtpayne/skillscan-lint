# Changelog

All notable changes to `skillscan-lint` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-04-20

### Added
- `-h` help shorthand
- GR-001 through GR-006 graph rules now visible in `skillscan-lint rules`
- `--badge-out` flag for shields.io lint badge generation
- Non-.md file rejection with clear warning

### Fixed
- PASS/FAIL summary text now matches exit code when `--fail-on warning` used
- Binary file crash (UnicodeDecodeError) replaced with graceful skip
- Build backend: hatchling (consistent with family)
