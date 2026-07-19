# Reader Tool Design

Reader is `status: planned` and in construction. It is not invocable in the
current release, and its declared workspace or database must not be created as
if a reader runtime existed.

The future design reserves `05_tools/reader/` for runtime material and
`06_indexes/databases/reader.db` for structured state. Instructions and
lifecycle declarations remain in `06_indexes/`. Registry `status: installed`
will be mandatory, but an implementation, dependencies, configuration, and a
permitted vault mode will also be required.

This file is explanatory design, not an operational contract.
