#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configure and check a password-protected Caddy frontend on a stable public IP."""
import argparse
import getpass
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request


def render_config(address, username, password_hash, upstream_port=8080, https_port=443):
    ipaddress.IPv4Address(address)
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,32}', username):
        raise ValueError('Invalid username')
    if not re.fullmatch(r'\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}', password_hash):
        raise ValueError('A bcrypt password hash is required')
    if not 1 <= int(upstream_port) <= 65535 or int(upstream_port) in (80, 443, 8081):
        raise ValueError('Invalid application port')
    origin = 'https://' + address + (':' + str(https_port) if https_port != 443 else '')
    return '''{
    admin off
}

%s {
    tls {
        issuer acme {
            dir https://acme-v02.api.letsencrypt.org/directory
            profile shortlived
        }
    }
    header {
        -Server
        Referrer-Policy no-referrer
        Cache-Control no-store
    }
    @webhook path /webhook
    @foreign_origin {
        header Origin *
        not header Origin %s
    }
    @cross_site {
        header Sec-Fetch-Site cross-site
        not {
            method GET
            header Sec-Fetch-Mode navigate
            header Sec-Fetch-Dest document
        }
    }
    handle @webhook {
        reverse_proxy 127.0.0.1:8081
    }
    handle {
        route {
            respond @foreign_origin 403
            respond @cross_site 403
            basic_auth {
                %s %s
            }
            reverse_proxy 127.0.0.1:%d {
                header_up Host 127.0.0.1:%d
                header_up -Origin
                header_up -Authorization
                header_up -Referer
            }
        }
    }
}
''' % (origin, origin, username, password_hash, upstream_port, upstream_port)


def configure(args):
    address = str(ipaddress.IPv4Address(args.ip))
    if not ipaddress.ip_address(address).is_global:
        raise SystemExit('A globally routable public IPv4 address is required')
    directory = Path(args.config_dir)
    directory.mkdir(parents=True, exist_ok=True)
    settings_file = directory / 'settings.json'
    settings = json.loads(settings_file.read_text(encoding='utf-8')) if settings_file.exists() else {}
    username = settings.get('username', 'aria')
    password_hash = settings.get('password_hash')
    if not password_hash or args.reset_password:
        first = getpass.getpass('Dashboard password (16-72 UTF-8 bytes; hidden): ')
        second = getpass.getpass('Repeat dashboard password: ')
        if first != second:
            raise SystemExit('Passwords do not match; configuration was not replaced')
        if not 16 <= len(first.encode('utf-8')) <= 72 or any(c in first for c in '\r\n\x00'):
            raise SystemExit('Use a password of 16-72 UTF-8 bytes without newlines')
        result = subprocess.run([args.caddy, 'hash-password'], input=first + '\n', text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        password_hash = result.stdout.strip()
    config = render_config(address, username, password_hash, args.upstream_port)
    # Validate the generated candidate before replacing any existing config.
    candidate = directory / 'Caddyfile.candidate'
    try:
        candidate.write_text(config, encoding='utf-8')
        candidate.chmod(0o640)
        subprocess.run([args.caddy, 'adapt', '--config', str(candidate), '--adapter', 'caddyfile', '--validate'],
                       stdout=subprocess.DEVNULL, check=True)
        candidate.replace(directory / 'Caddyfile')
        settings_file.write_text(json.dumps(dict(ip=address, username=username, password_hash=password_hash), indent=2) + '\n', encoding='utf-8')
        settings_file.chmod(0o640)
    finally:
        candidate.unlink(missing_ok=True)
    print('Dashboard username: ' + username)
    print('Password stored as bcrypt hash; plaintext is not stored.')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_status(config_dir, wait=0):
    settings = json.loads((Path(config_dir) / 'settings.json').read_text(encoding='utf-8'))
    address = str(ipaddress.IPv4Address(settings['ip']))
    base = 'https://' + address
    opener = urllib.request.build_opener(NoRedirect)
    deadline = time.monotonic() + wait
    while True:
        try:
            probes = [('/dashboard', 401, {}), ('/api/status', 401, {}),
                      ('/dashboard.js', 401, {}), ('/webhook', 403, {}),
                      ('/dashboard', 401, {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'}),
                      ('/api/status', 403, {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty'})]
            for path, expected, headers in probes:
                try:
                    with opener.open(urllib.request.Request(base + path, headers=headers), timeout=5) as response:
                        code = response.status
                except urllib.error.HTTPError as exc:
                    code = exc.code
                    if expected == 401 and not exc.headers.get('WWW-Authenticate', '').startswith('Basic '):
                        raise RuntimeError('Password challenge is missing') from None
                    exc.close()
                if code != expected:
                    raise RuntimeError('%s returned %s; expected %s' % (path, code, expected))
            print('Dashboard URL: ' + base + '/dashboard')
            print('Username: ' + settings['username'])
            print('HTTPS certificate verified. Dashboard/API require a password; webhook remains independent.')
            print('External-link navigation reaches login; cross-site API requests are blocked.')
            print('Now verify login from your browser outside the VPS.')
            return
        except (OSError, RuntimeError) as exc:
            if time.monotonic() >= deadline:
                raise SystemExit('Public HTTPS is not ready: %s\nInspect: journalctl -u aria-dashboard -n 60 --no-pager\nPorts 80/443 must also be allowed in the VPS provider firewall.' % exc)
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    configure_parser = sub.add_parser('configure')
    configure_parser.add_argument('--ip', required=True)
    configure_parser.add_argument('--upstream-port', type=int, default=8080)
    configure_parser.add_argument('--caddy', required=True)
    configure_parser.add_argument('--config-dir', default='/etc/aria-dashboard')
    configure_parser.add_argument('--reset-password', action='store_true')
    status_parser = sub.add_parser('status')
    status_parser.add_argument('--config-dir', default='/etc/aria-dashboard')
    status_parser.add_argument('--wait', type=int, default=0, choices=range(61), metavar='0..60')
    args = parser.parse_args()
    if args.command == 'configure':
        configure(args)
    else:
        check_status(args.config_dir, args.wait)


if __name__ == '__main__':
    main()
