# Project Rules

Single-file Python script that exports Glean Go Links via the paginated
`POST /rest/api/v1/listshortcuts` API. See README.md for the full flow.

## Constraints

- Keep the script **read-only**. Never call shortcut create/update/delete endpoints.
- Standard library only for HTTP (`urllib`); `python-dotenv` is the only third-party
  dependency. Do not add `requests` or an SDK without asking.
- Target Python 3.10+. Use built-in generics (`dict[str, Any]`, `str | None`), not `typing.Dict`/`Optional`.
- Never print, log, or include in error messages the value of `GLEAN_API_TOKEN`
  or the `Authorization` header. HTTP error bodies are OK to print.
- Never commit `.env` or the generated `glean_golinks_export.*` files. They are gitignored; keep it that way.
- Do not add customer or company names to code or docs; keep examples generic (`example.com`).

## Verify

```bash
python3 -m py_compile export_glean_golinks.py
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python export_glean_golinks.py   # with no .env, must fail with "GLEAN_BASE_URL is not set"
```

There is no test suite. If you change pagination or CSV logic, add a stub-based
test rather than hitting the real API.

## Docs

- Changing CLI flags, env vars, or output columns requires updating README.md
  and the module docstring in `export_glean_golinks.py` together.
- Field names must match the `Shortcut` schema in Glean's OpenAPI spec:
  https://github.com/gleanwork/open-api/blob/main/final_specs/client_rest.yaml
