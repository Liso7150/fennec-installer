# Changelog

All notable changes to fennec-installer, the bootstrap shim and setup hub.

The sections below carry the published tag each change actually shipped in
(`Liso7150/fennec-installer`, `v0.1.0` … `v0.9.0`). An earlier revision of this
file numbered the same history on a 1.x/2.x ladder that was never published;
those tags still exist locally (`v1.2.0` … `v2.0.0`) and each one points at the
same commit as a published `v0.x` tag. Dates are the tag publish dates.

## [Unreleased] — 1.0.0 in preparation

Nothing at 1.0.0 is published. The newest release here is `v0.9.0`
(2026-11-11T19:29Z). Measured on the working tree: 50 tests passed plus 10
subtests (`python -m pytest -q`, 2026-11-21; the hub's `installer` lane runs
`python -m unittest discover -s tests` and reports the same 50).

### Added
- `updater.py`: self-update from the GitHub releases of this repo, with
  `--experimental` polling the `main` branch instead of a tag
- The setup hub resolves to the suite sibling checkout before falling back to
  `~/Fennec-Environment-Setup`, so a suite install never clones a second hub
- README heroes (installer and Android) and this changelog
- `--web-python`, so every key in the hub's shared config set can be pinned from
  the command line rather than only by editing `config.json`

### Changed
- Version 1.0.0; `install.py` stays the compatibility entry point and defaults to
  `--fetch-only`
- `browser-outlets` installs Fennec's own browser venv beside the `--openbot-url`
  checkout it already cloned. The deleted `jev` lane's flags (`--jev-root`,
  `--web-engine`) and the unused `--native-target` are gone: passing one is now a
  refusal, not a silently ignored setting

### Fixed
- The bootstrap test assertion that no longer matched the bootstrap

## [0.9.0] - 2026-11-11

### Changed
- The bootstrap prints the artifact names the release actually ships

## [0.8.0] - 2026-11-11

### Added
- Optional browser outlets in the install plan
- Correct artifact names in the completion message

## [0.7.1] - 2026-11-11

Version bump only.

## [0.7.0] - 2026-11-11

Version bump only.

## [0.6.0] - 2026-11-11

Version bump only.

## [0.5.0] - 2026-11-11

### Added
- `--version` reports the installer version

## [0.4.0] - 2026-11-11

### Changed
- Default the install root to `~/Fennec` and run everything on PATH python
- A drive picker replaces the `D:` defaults in bootstrap and migration

## [0.3.0] - 2026-11-10

### Added
- Deferred Colibri → Fennec local migration

### Changed
- Rebrand the installer and the Android scaffold to Fennec

## [0.2.0] - 2026-11-10

### Changed
- The docs describe the sidecar IR download instead of an optimum export step

## [0.1.0] - 2026-11-10

The first published release. It carries the pre-tag history below.

### Added
- `--update` for suite checkouts alongside the existing fetch/install modes
- An install destination prompt that keeps every file on the device
- Termux runs the core locally
- `install.py` delegates to the portable bootstrap, with entry-point tests
- Features documented in the README

### Credits
- Initial commit as colibri-installer (Colibri suite; JustVugg/colibri +
  lyogavin/airllm)
