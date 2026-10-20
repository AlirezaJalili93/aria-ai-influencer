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

## OpenAI character voice replaces dashboard ElevenLabs

The user subsequently supplied successful `--status` output from the VPS for the webhook addition: the public callback is reachable and dashboard/API routes are blocked. That infrastructure result does not verify the following speech change or any paid provider credentials.

- Python 3.9.25: all 26 tests pass, including seven new voice tests for OpenAI-only active key selection, Persian input and persona instructions, exact `/audio/speech` endpoint/Bearer authentication, saved MP3, voice/speed/style persistence across restart, retained daily settings, paused/exhausted keys, input limits, provider error redaction, rejected non-audio/empty bodies, and concurrent-call rejection. Binary speech responses do not create invented token usage.
- Chromium 153 end-to-end on the real local app: entered an OpenAI test key in the dashboard, verified key field clearing, selected voice/speed/style, generated through a fake local speech endpoint, downloaded the persisted MP3, played it in the browser, verified that the 10-second polling cycle preserves the playing audio element, reloaded to recover settings/history, and checked a sanitized HTTP 401 error. Desktop 1440×1100 and mobile 390×844: no page errors, no external browser requests, no mobile horizontal overflow. Test audio is a real playable MP3 tone made with ffmpeg, not an OpenAI/Persian voice sample.
- JavaScript syntax and Git whitespace checks pass. Original character/reference assets and legacy ElevenLabs helper are preserved; only the live dashboard's speech route uses OpenAI.
- No real OpenAI speech call, paid request, listening evaluation of Persian speech, or VPS voice rollout has been performed. Access to the model and voice, pronunciation, cost and credentials still require a real generation using the user's API key on the server. The updater does not restart the public webhook tunnel.

## Stable public HTTPS dashboard

The user supplied successful VPS rollout logs for f941572: active daemon, health 200, typography checks and 58-file manifest verification. The following public HTTPS frontend still requires installation on that VPS.

- Official Caddy 2.11.7 Linux amd64 archive was downloaded and SHA-256 verified against GitHub's release asset digest (`727b91701a392de6ebc5027509f548bf39979e5216340d0faed8fa5e69c84f8b`). The production Caddyfile adapts to an explicit public IPv4 ACME issuance policy using Let's Encrypt and profile `shortlived`; it does not use the internal issuer.
- All 32 tests pass on Python 3.9.25 with `ARIA_TEST_CADDY=/tmp/aria-caddy`. Six new tests cover config validation, an actual Caddy HTTPS frontend plus the actual agent and webhook relay, anonymous denial for pages/API/assets/media, valid and wrong passwords, browser-origin API writes, cross-origin rejection, and public webhook challenge/HMAC independence. The test-only local CA is explicitly trusted by the Python HTTPS client and is never installed into the system trust store. Caddy HTTPS integration tests are skipped when no test binary is supplied.
- Chromium 153: authenticated HTTPS page, local images/fonts/JS, browser-origin settings update, saved PNG draft, authenticated PNG download, anonymous media 401, persistence after page reload, mobile 390px without horizontal overflow, and zero page JavaScript errors. Browser fixture uses the local test CA, not a real Let's Encrypt certificate; only the test context permits that local certificate. Production status verification uses normal certificate validation.
- Installer shell syntax, generated systemd unit syntax and Git whitespace checks pass. The installer refuses occupied web ports, scopes its binary/config/state/service separately, preserves existing app/tunnel/data, and records only added web firewall services without flushing rules.
- No public IP certificate has been issued by this execution environment, and no provider firewall or live VPS HTTPS access has been verified. The installer checks the real certificate and anonymous authentication challenge after deployment; final external reachability and browser login must be checked from outside the VPS. The independent service is enabled for boot and Caddy manages renewal while the server, network and challenge ports remain available.
