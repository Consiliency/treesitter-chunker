# Native packaging — suspended for v5

The owner approved PyPI-only v5 distribution on 2026-09-11. The Debian, RPM and
Homebrew recipes in this directory are retained as repair inputs; they are not
supported v5 installation methods. Version, dependency, architecture and checksum
repairs are still required. Do not use these recipes to publish v5 packages.

The native workflow has no tag/build/upload path, and manual dispatch fails.
Re-enablement requires all [native rebuild gates](../docs/packaging.md#native-distribution-rebuild-backlog),
including clean platform installation evidence and gated artifact publication.
Local source builds and local grammar compilation remain available.
