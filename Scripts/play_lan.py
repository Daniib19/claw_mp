#!/usr/bin/env python3
"""Launch the patched native OpenClaw game in a LAN cooperative session."""
import argparse
import ipaddress
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

def validate_archive(path):
    if not path.is_file():
        raise ValueError(f'Copy the original game archive to {path}')
    with path.open('rb') as f:
        header = f.read(139)
    if len(header) < 139:
        raise ValueError('CLAW.REZ is truncated: its archive header is incomplete.')
    offset, size = struct.unpack_from('<II', header, 131)
    if size == 0:
        raise ValueError('CLAW.REZ is an empty archive. Supply the full original game archive containing levels and sprites.')
    if offset + size != path.stat().st_size:
        raise ValueError('CLAW.REZ is incomplete or invalid: archive directory does not match file size.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--host', action='store_true', help='start a local server and play')
    mode.add_argument('--join', metavar='IP', help='join an existing server by IPv4 address')
    mode.add_argument('--menu', action='store_true', help='open the game menu to Host or Join (default)')
    mode.add_argument('--server', action='store_true', help='run only the dedicated server')
    parser.add_argument('--port', type=int, default=27888)
    parser.add_argument('--binary', type=Path, help='path to your freshly compiled game executable')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be 1..65535')
    server_cmd = [sys.executable,str(ROOT/'server/lan_server.py'),'--port',str(args.port)]
    if args.server:
        return subprocess.call(server_cmd)
    address = args.join or '127.0.0.1'
    try:
        ipaddress.IPv4Address(address)
        validate_archive(ROOT/'Build_Release/CLAW.REZ')
    except ValueError as exc:
        parser.error(str(exc))
    binary = args.binary or ROOT/'Build_Release'/('openclaw.exe' if os.name=='nt' else 'openclaw')
    binary = binary.resolve()
    if not binary.is_file():
        parser.error('Build the patched game first; see MULTIPLAYER.md. Upstream prebuilt binaries do not include LAN support.')
    env = os.environ.copy()
    env['OPENCLAW_PORT'] = str(args.port)
    if args.host or args.join:
        env['OPENCLAW_SERVER'] = address
    else:
        env.pop('OPENCLAW_SERVER', None)
    local_libs=ROOT/'.local-deps/usr/lib/x86_64-linux-gnu'
    if local_libs.is_dir() and sys.platform.startswith('linux'):
        env['LD_LIBRARY_PATH']=str(local_libs)+os.pathsep+env.get('LD_LIBRARY_PATH','')
    server = None
    try:
        if args.host:
            server = subprocess.Popen(server_cmd)
            deadline=time.monotonic()+5
            while True:
                if server.poll() is not None:
                    parser.error('The server could not start. Check whether the port is already in use.')
                try:
                    with socket.create_connection(('127.0.0.1',args.port),timeout=0.2): pass
                    break
                except OSError:
                    if time.monotonic()>deadline:
                        parser.error('The local server did not become ready.')
                    time.sleep(0.05)
        if args.host or args.join:
            print(f'Joining {address}:{args.port}. The host can start a shared mission from Multiplayer.',flush=True)
        else:
            print('Open Multiplayer in the game menu to Host or Join LAN co-op.',flush=True)
        return subprocess.call([str(binary)],cwd=ROOT/'Build_Release',env=env)
    finally:
        if server:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait()

if __name__=='__main__':
    try: sys.exit(main())
    except KeyboardInterrupt: sys.exit(130)
