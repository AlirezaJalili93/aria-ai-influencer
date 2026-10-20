#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find the current Quick Tunnel URL and verify its public route isolation."""
import argparse
import re
import subprocess
import time
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_routes(base):
    opener = urllib.request.build_opener(NoRedirect)
    for path, expected in [("/dashboard", 404), ("/api/status", 404), ("/", 404), ("/webhook", 403)]:
        try:
            with opener.open(base + path, timeout=4) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
        if status != expected:
            raise RuntimeError("Route %s returned %s; expected %s" % (path, status, expected))


def current_url():
    service = "aria-webhook-tunnel.service"
    subprocess.run(["systemctl", "is-active", "--quiet", service], check=True)
    invocation = subprocess.check_output(
        ["systemctl", "show", service, "--property=InvocationID", "--value"], text=True
    ).strip()
    if not re.fullmatch(r"[a-f0-9]{32}", invocation):
        raise RuntimeError("No running tunnel invocation")
    logs = subprocess.check_output(
        ["journalctl", "--no-pager", "-o", "cat", "_SYSTEMD_INVOCATION_ID=" + invocation], text=True
    )
    urls = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com\b", logs)
    if not urls:
        raise RuntimeError("Tunnel has not announced a public URL yet")
    return urls[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait", type=int, default=0, choices=range(0, 61), metavar="0..60")
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        try:
            url = current_url()
            check_routes(url)
            print("Callback URL: " + url + "/webhook")
            print("Public checks passed: dashboard/API blocked; webhook awaits Meta verification.")
            print("Temporary URL: recheck after every tunnel restart and update the Meta callback.")
            return
        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            if time.monotonic() >= deadline:
                raise SystemExit("Tunnel not verified: %s\nInspect: journalctl -u aria-webhook-tunnel -n 40 --no-pager" % exc)
            time.sleep(2)


if __name__ == "__main__":
    main()
