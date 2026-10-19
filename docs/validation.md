# Validation of the restored Aria studio

- Python 3.9.25: `python -m unittest discover -s tests -v` covers existing state, server/daemon startup, webhook signatures, origin restrictions, local HTTP AI routing, token accounting, media scheduling/cancellation, persistent drafts/settings, once-per-day production, failed-job accounting, environment key pause/budget persistence, local Vazirmatn/RAQM, and image generation through a fake local image gateway.
- Browser end-to-end: Chromium 153, desktop 1440×1100 and mobile 390×844. Verified all four tabs, exact recovered character assets, local fonts, real backend API with fake local AI, separated simulator, escaped chat text, saved content packs, PNG download and persisted draft, MP4 job/download, schedule/cancel, saved automation after reload, and no horizontal overflow on all four mobile tabs.
- Exported PNG: 1080×1920; inspected Persian/Latin mixed text and local font rendering.
- Rendered MP4: real Python/Pillow/OpenCV renderer, H.264 via available ffmpeg, 1080×1920, 5 seconds; inspected with ffprobe.
- Skill frontmatter/content validated with Skill Creator quick_validate.
- Shell syntax: `bash -n scripts/update_from_git.sh scripts/server_git_deploy.sh`.
- No real AI key, paid media API, Meta account, or Instagram publication was used in local verification. Live external integration checks remain dependent on credentials and Meta configuration.
- Direct SSH to the user's server returned `Network is unreachable`; server installation is not represented as completed.

[Desktop](screenshots/dashboard.png) · [Mobile](screenshots/mobile.png)
