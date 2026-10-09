"""The lab's importable package. `env` is the provenance module every experiment uses
(banner, save_result and the outcome blocks); the lab's own shared code goes beside it.
Code that needs a heavy library is imported inside the experiment that uses it, after
`env.require_sage()` (or the lab's equivalent guard)."""
