# Maintaining BitPolito Craft

BitPolito Craft is a browser-first customization of Deckcraft. `main` contains our
application; `upstream` points to `storytold/deckcraft`. Upstream updates are merges,
not copied source or squash commits. Crate/package names remain upstream-compatible.

## Current design source

The source is [Presentazioni BitPolito](https://www.figma.com/design/QJ5ozI9rgKfKxTI6xoJkFa).
**Figma is not connected. The committed layouts are original bootstrap layouts,
not audited reproductions of that file.** Official CC0 logos/icons come from the
published BitPolito media kit at the commit recorded in provenance.json. Do not
mark the package audited until the original designs have been compared.

`brand/bitpolito/` is the update boundary:

- `config.json`: application title, colors, font, default template and brand version.
- `tokens.json`: reference design tokens; editable template definitions record the
  resolved values, so a token change must be applied to the affected definitions.
- `templates.json`: eight native layouts and three stable `bitpolito-*` starters.
- `assets.json`: stable asset IDs, labels, categories and runtime paths.
- `sources/`: SVG originals; `runtime/`: PNG files and a generated Rust registry.
- `mapping.json`: explicitly approved Figma IDs and placeholder roles; empty until audited.
- `provenance.json` and `LICENSE`: design source/version, hashes and asset rights.

Use Inter Regular/Bold. Do not redistribute SF Pro or flatten complete slides.
Text, rectangles and placeholders belong in native template definitions; logos and
illustrations belong in image assets. Runtime PNGs should be exported at 3× their
intended slide size (record `slideSize: [width,height]` in new catalog entries).
The bootstrap media-kit PNGs retain their published dimensions. The favicon uses
the official bull SVG, which the browser can render directly.

## Manual design updates (the active workflow)

1. Export approved slide references, logos and icons from the original Figma file.
   Keep SVG originals and transparent PNGs. Do not export fonts.
2. Copy the existing brand package to a directory outside the checkout; replace the
   selected assets and update tokens/templates. For slide references, map text
   boxes to `title`, `subtitle`, `body`, `caption` or `footer`; convert positions to
   960×540. Keep stable IDs when a source layer is renamed. Decorative graphics may
   be placed using a layout's `decorations: [{asset, rect: [x,y,w,h]}]` list.
3. Record the original file version/node IDs in provenance, retain all required
   license texts, bump `brandVersion`, and update ATTRIBUTION.md for added assets.
4. Run `python3 scripts/bitpolito/brand.py import-manual /absolute/export-package`.
   The entire package, including complete SVGs, PNG checksums and complete image data, is validated
   before an atomic directory swap. Invalid input
   preserves the previous package. Reimporting identical exports produces no diff.
5. Build and inspect previews, then run the visual reference updater locally only:
   `python3 scripts/bitpolito/visual-check.py --update`. Review the images under
   `.local/visual/`; submit the source changes and reviewed references in a PR.
   Another maintainer must approve the current commit before merging brand changes.

For a simple asset replacement, edit the versioned files directly and run
`python3 scripts/bitpolito/brand.py build`; generated hashes, registry and HTML
are rebuilt. This command never connects to Figma.

## Optional API import

Later, populate all eight mappings in mapping.json. Each layout entry contains
`id`, `label`, `nodeId`, `placeholders: [{nodeId,role}]`, and optional
`decorations: [{nodeId,asset}]`. Each asset entry contains `id`, `nodeId`, `label`,
and `category`. Set the package license and optional pinned Figma `version`.

The importer supports plain left-aligned text, solid backgrounds, and explicitly
mapped decorative assets. Mixed text styles, unsupported effects, missing nodes,
or unaccounted visible elements fail visibly rather than silently losing design.

Set a read-only `FIGMA_TOKEN` in the environment, then run
`python3 scripts/bitpolito/import_figma.py`. For Actions, store it as a repository
secret and run **Import Figma**. The workflow opens a design PR and never enables
automatic merging. API access is unnecessary for normal builds or site visitors.

## Building and validating

Use Rust 1.97.1, Trunk 0.22.1, Node 22.17.0, and the committed Cargo/npm locks.
Install the Linux development dependencies listed in bitpolito-ci.yml. Check out
`storytold/craft-fonts` at `37827adc41fd165f9a9234ac40f94dbad353aa69`, then set
`CRAFT_FONTS_DIR` to that absolute checkout and `CRAFT_FONTS_REQUIRED=1`.

Run:

```sh
python3 scripts/bitpolito/brand.py check
python3 -m unittest discover -s tests/bitpolito -p 'test_*.py'
cargo xtask ci
python3 scripts/bitpolito/visual-check.py
bash scripts/bitpolito/build-web.sh
```

Serve `dist/web` over localhost or HTTPS. Install the pinned browser tests with
`npm ci --prefix tests/bitpolito/browser`, install Playwright Chromium/Firefox, and
run `node tests/bitpolito/browser/node_modules/@playwright/test/cli.js test --config tests/bitpolito/browser/playwright.config.js`.
CI runs headed browsers under `xvfb-run` so Firefox can create its WebGL2 context
on Ubuntu; see [Playwright's CI guidance](https://playwright.dev/docs/ci#running-headed).
Tests stop on the first failure and retain screenshots/traces. Compiled inputs
are cached before browser validation, while deployment still requires every check.

The browser tests opt into `?automation`, which exposes `window.bitpolito.execute`
for same-origin testing. Ordinary sessions do not expose this command bridge.

Public command additions are `bitpolito.assets` and `bitpolito.insertAsset`.
Existing `file.templates` and `file.new` accept the new starters without changing
upstream starters or file formats.

## Local recovery

Every five seconds, and when a tab is hidden or left, the browser stores changed native documents and the active
index in IndexedDB. Web Locks isolate sessions between tabs. Reloading restores
that tab; reopening the site can reclaim the newest session that no live tab owns.
Explicitly closed documents are removed. Transactions are serialized. Unsupported
storage or a corrupt snapshot displays a persistent warning; the existing draft
is preserved and save/download remains available. Recovery is not cloud storage,
may be cleared by browser settings, and does not preserve undo history.

## Hosting, protections and updates

A complete **BitPolito validation** run must pass before activation. It runs the
upstream quality gates, importer checks, visual references, a release WASM build,
and real browser tests. The successful `main` build is retained as an artifact for
90 days. Production deployment consumes this artifact, never rebuilding untested
source. An outdated run cannot overwrite a newer main deployment.

Run `python3 scripts/bitpolito/configure-repository.py` after successful validation
on the current main. It enables auto-merge, protects main with `validation` and
`design-review`, prevents force pushes and deletion, and configures Pages.
Set repository variable `BITPOLITO_ENABLED=true` to allow production deployment.

To enable daily upstream sync, create a repository-scoped GitHub App with contents
read/write, pull requests read/write and workflows read/write permissions. Install
it on this fork; store `UPDATER_APP_ID` and `UPDATER_APP_PRIVATE_KEY` as Actions
secrets. Then set `BITPOLITO_SYNC_ENABLED=true`. The daily integration PR merges
only when protected-branch checks pass and it is up to date. Conflicts produce a
draft PR for maintainer resolution; production stays unchanged. Do not squash
upstream integration PRs. Existing inherited upstream CI workflows remain intact.

Use **BitPolito rollback** with a successful main validation run ID to restore a
retained artifact. Verify the downloaded release's build-info.json. Expired
artifacts cannot be restored; rebuild and revalidate that commit instead.

## Transfer to BitPolito

Transfer this same fork; do not create a second fork in the destination account.
Update `origin`, the GitHub App installation, secrets, Pages permissions and
repository variables; rerun validation and verify Pages before switching DNS.
Workflows derive owner/repository from GitHub context. The upstream fork connection
and history remain intact. GitHub Pages URLs do not redirect after a transfer.
