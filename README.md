# Shibutzim

App for shifts and payments management: shift scheduling and pay for small teams of hourly workers.

## Assistant

A chat (the Assistant screen) answers questions about shifts, hours, pay and the company policy, and prepares a
schedule proposal for managers. It calls tools that run the same services as the app, as the signed-in user; policy
answers come from the employee handbook and name the section they used. See
[docs/architecture.md](docs/architecture.md) §6.4–§6.7.

To enable it, put a Gemini API key in `.env` (see `.env.example`), then:

```bash
cd server
uv run python scripts/seed.py              # demo data
uv run python scripts/ingest_handbook.py   # embeds the handbook once
uv run python -m evals.run --list          # the fifteen eval cases; --only <ids> runs a few
```

Without a key every other screen works and the assistant answers "not available". Tests never call a real model.
