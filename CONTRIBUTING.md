# Contributing

Use Python 3.10 or newer. There are no runtime dependencies.

```sh
python -m venv .venv
# Activate the virtual environment using your shell's usual command.
python -m pip install -e .
python -m unittest discover -s tests -v
```

Small fixes can be proposed directly as pull requests. For a new host adapter,
installation/removal feature, or major CLI change, open an issue describing the
workflow first. Include the behavior change and the checks you ran in your PR.

Preserve the distinction between unknown usage and observed inactivity. Never
infer invocations from file timestamps. Tests should use synthetic events and
temporary directories, without reading the contributor's host logs or changing
their installed skills. Keep source skills unchanged during audits and drafts.

Do not commit real usage databases, session logs, credentials, or private skill
contents. An audit report can contain source text; inspect it before sharing.
