# Contributing

## AI-assisted development

This plugin is written **largely by hand, with limited AI assistance**. AI assistance is used occasionally, for isolated changes, refactors and tests, rather than as the primary means of development. Technical direction, review, testing and acceptance of changes remain the responsibility of the maintainer.

AI use is disclosed at the repository level rather than on individual commits, so commit messages and pull requests carry no co-authorship trailers or generated-with footers.

The level of assistance differs across the project; each Kalinka repository states its own in its `CONTRIBUTING.md`.

If AI assistance played a significant part in a pull request you send, a note in the description is welcome — it helps direct review.

## Sending a change

Fork the repository, create a feature branch, and open a pull request describing the change. Run the test suite with `PYTHONPATH=src python -m pytest tests/` — the package is not installed into the environment by default.

Releases are tag-triggered from this repository's own CI; push a `kalinka-plugin-qobuz-v*` tag to publish.

## Licensing

Apache License 2.0 — see `LICENSE` and `NOTICE`.
