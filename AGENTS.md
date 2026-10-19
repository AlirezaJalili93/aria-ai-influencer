# Aria project instructions

Preserve the original reference in `docs/reference/`, the playbook, legacy HTML files, character images, and user data. Do not reset/delete server data or overwrite `.env` credentials.

Use `.agents/skills/persian-rtl-vazirmatn/SKILL.md` for Persian content. Use UTF-8, RTL, and the bundled Vazirmatn fonts in `assets/fonts/`. Read `character/aria.json` before changing the persona. Keep `instagram_ai_agent.py` and `src/instagram_ai_agent.py` identical.

The operational dashboard is `web/dashboard.html` + `web/dashboard.js`. All credentials and live operations go through the same-origin local backend. Show simulator/template states explicitly; do not populate real usage, followers, schedules or connection status with sample numbers.

Test with `python -m unittest discover -s tests -v`. The admin service binds to loopback and is opened through an SSH tunnel. Never publish port 8080 as an unauthenticated admin panel.
