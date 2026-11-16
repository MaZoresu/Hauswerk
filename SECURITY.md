# Sicherheit

- Dieses Repository hat **keine Secrets**. Workflows laufen mit Leserechten; nur der Release-Workflow darf Releases anlegen – nur auf `main`, nur vom Besitzer ausgelöst.
- Alle GitHub Actions sind auf einen festen Commit gepinnt; Dependabot schlägt Updates als Pull Request vor.
- Checkouts speichern kein Zugriffstoken in `.git/config` (`persist-credentials: false`).
- Verdächtige Änderungen (z. B. Branch `wfx-docs`, Branches `chore/<8 Zeichen>`, Commits wie „ci: refresh build cache“, „chore: add ci helper“) bitte als Issue melden.
