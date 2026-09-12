#!/usr/bin/env python3
"""Measure cancellation on an idle loopback candidate using a nonclinical prompt."""

import argparse
import json
import socket
import time
import urllib.parse
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--model', required=True)
parser.add_argument('--phase', choices=['generation', 'prefill'], default='generation')
parser.add_argument('--output', required=True)
args = parser.parse_args()
base = args.url.rstrip('/')
url = urllib.parse.urlsplit(base)
if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost'):
    parser.error('--url must point to an HTTP loopback candidate')

def request(path, payload=None):
    req = urllib.request.Request(base + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)

def slots():
    return request('/slots?model=' + urllib.parse.quote(args.model))

def decoded(slot):
    token = slot.get('next_token') or {}
    if isinstance(token, list):
        token = token[0] if token else {}
    return token.get('n_decoded', 0)

initial_slots = slots()
assert not any(s['is_processing'] for s in initial_slots), 'Candidate is already busy'
initial_decoded = decoded(initial_slots[0])
payload = {'model': args.model, 'prompt': 'Write an endless list of integers starting at one.',
           'n_predict': 512, 'ignore_eos': True, 'stream': False}
if args.phase == 'prefill':
    payload['prompt'] = ('A unique fresh context for cancellation. ' * 180) + ' Continue.'
prompt_tokens = len(request('/tokenize', {'model': args.model, 'content': payload['prompt'],
                                        'add_special': True})['tokens'])
body = json.dumps(payload).encode()
connection = socket.create_connection((url.hostname, url.port or 80), timeout=10)
try:
    connection.sendall((f'POST /completion HTTP/1.1\r\nHost: {url.netloc}\r\n'
                        f'Content-Type: application/json\r\nContent-Length: {len(body)}\r\n'
                        'Connection: close\r\n\r\n').encode() + body)
    deadline = time.monotonic() + 90
    active = None
    while time.monotonic() < deadline:
        active = next((s for s in slots() if s['is_processing']), None)
        if active:
            if args.phase == 'prefill' and active['n_prompt_tokens'] < prompt_tokens:
                break
            if args.phase == 'generation' and decoded(active) >= 2 and decoded(active) != initial_decoded:
                break
        time.sleep(.1)
    else:
        raise RuntimeError('Did not observe the required active model phase')
finally:
    connection.close()
start = time.monotonic()
idle = False
observations = []
while time.monotonic() - start < 5:
    current = slots()
    busy = [s for s in current if s['is_processing']]
    elapsed = time.monotonic() - start
    observations.append({'seconds': round(elapsed, 3),
                         'processing': bool(busy),
                         'decoded': decoded(current[0])})
    if not busy:
        idle = elapsed <= 5
        break
    time.sleep(.2)
report = {'phase': args.phase, 'model': args.model,
          'activeTask': active['id_task'], 'slotDecodedSnapshotAtDisconnect': decoded(active),
          'promptTokens': prompt_tokens, 'promptTokensAtDisconnect': active['n_prompt_tokens'],
          'idleWithinFiveSeconds': idle, 'observations': observations}
Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
raise SystemExit(0 if idle else 1)
