![CI](https://github.com/No-Signal/iotawattpy/actions/workflows/ci.yml/badge.svg)

> **Fork notice:** this is a modified fork of
> [home-assistant-libs/iotawattpy](https://github.com/home-assistant-libs/iotawattpy),
> forked at commit `42d4d6e` (the commit after `v0.3.0`). It is renamed to
> `iotawattpy-nosignal` (import package `iotawattpy_nosignal`) so it cannot clash
> with the upstream `ha-iotawattpy` package. It is **not** published to PyPI; it
> is bundled into the [No-Signal/ha-iotawatt](https://github.com/No-Signal/ha-iotawatt)
> Home Assistant custom integration. The changes are listed in
> [CHANGELOG.md](CHANGELOG.md). Licensed under GPL-3.0-or-later, like upstream.

# iotawattpy-nosignal
 Python interface for the IoTaWatt device

## Bundling

The package is copied verbatim into the integration, so it must keep two
properties, both enforced by `tests/test_bundling.py`:

- every import of the package's own modules is relative
  (`from .connection import Connection`), never absolute;
- its only runtime dependency is `httpx`.

## Releasing

Releases are not published to PyPI. To release:

1. Bump the version on `main`: `uv version <new-version>` (updates
   `pyproject.toml` and `uv.lock`), add a `CHANGELOG.md` entry, then commit.
2. Create an annotated `v<new-version>` tag (e.g. `v0.4.0`), push it and
   create a GitHub release from it.
3. The release workflow builds the package and checks that it installs and
   imports. It fails if the tag does not match the project version.
