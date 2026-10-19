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

## FriBiDi runtime installation fix

Python 3.9.25: 14 tests pass, including the typography probe's missing-dependency error and native Persian/Latin rendering with both bundled fonts. A temporary test-only dlopen interceptor reproduces RAQM=False by preventing Pillow from loading FriBiDi. Running the installer's actual dependency block with a package-manager stub then restores the library visibility and passes the real render probe. The test does not claim an AlmaLinux host install; the user's server still needs the updated installer run.

## Webhook-only Quick Tunnel

The user subsequently supplied successful AlmaLinux deployment logs for `c53b11b8b47c69e43affa9194f54ede4043c9dc1`: FriBiDi installed, both typography probes passed, daemon active, health 200, and 51 files verified. The following tunnel addition has not yet been installed on that VPS.

- Python 3.9.25: all 19 tests pass. Five new tests exercise a real gateway against the real local backend: Meta verification challenge, byte-exact Persian JSON HMAC acceptance, missing/invalid signatures, denied dashboard/API/static/media/path variants even with a forged localhost Host header, unsupported methods, oversized/malformed/ambiguous framing, public route-probe validation, and upstream failure returning 502.
- Both generated unit definitions pass `systemd-analyze verify` (using a local executable in place of the not-yet-installed cloudflared executable). Installer passes `bash -n`; diff passes `git diff --check`.
- The official RHEL repository definition was retrieved and checked: HTTPS package repository with `gpgcheck=1`. No RPM install, systemd service start, real Cloudflare public tunnel, Meta callback registration, or Instagram account verification is claimed from local checks.
- SSH to the VPS still returns `Network is unreachable` from the execution environment. Run the supplied installation block on the VPS; the installer then checks both local and actual public route isolation before reporting a Callback URL.
