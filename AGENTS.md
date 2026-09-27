# Wealth Command Center implementation rules

- Preserve ownership checks on all profile, journal and future stored-data APIs. Never expose raw session tokens/passwords to logs or model prompts.
- Use `engine.py` for all calculation consumers; do not duplicate Swiss logic in the UI, agent, renderer or Stellarium adapter.
- A changed astronomical convention or symbolic rule needs a new framework version, provenance and explicit migration.
- Unverified custom boundaries/correspondences must remain missing or provisional, never guessed from illustrative examples.
- Keep all six language catalogs in sync. Dynamic raw engine fields may be inspectable as technical source data, but actionable UI text needs translations.
- Cloud AI requires per-request consent. Desktop actions require explicit user actions and stay disabled on public hosts.
- Run Python tests and lint, then the browser smoke workflow for UI/API changes. Preserve user data and do not publish without authorization.
