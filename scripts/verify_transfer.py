#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify Git-delivered code/resources without reading private state or keys."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'docs/transfer_manifest.json').read_text(encoding='utf-8'))
errors=[]
for relative, expected in manifest['files'].items():
    path = ROOT / relative
    if not path.is_file(): errors.append(relative + ': missing')
    elif hashlib.sha256(path.read_bytes()).hexdigest() != expected: errors.append(relative + ': hash mismatch')
if (ROOT/'instagram_ai_agent.py').read_bytes() != (ROOT/'src/instagram_ai_agent.py').read_bytes(): errors.append('Python entrypoints differ')
if errors: raise SystemExit('\n'.join(errors))
print('Verified %d project files against SHA-256 transfer manifest.' % len(manifest['files']))
print('Private .env, database, and generated media are outside the Git manifest.')
print('Original Gemini MP4 attachment remains unavailable; see docs/reference/README.md.')
