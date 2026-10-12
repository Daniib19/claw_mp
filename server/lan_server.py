#!/usr/bin/env python3
"""OpenClaw LAN cooperative session server. Python 3.10+, no dependencies."""
import argparse
import asyncio
import math
import re
import socket
from dataclasses import dataclass, field

MAX_PLAYERS = 8
MAX_LINE = 512
TOKEN = re.compile(r"^[A-Za-z0-9_./\\:-]{1,180}$")

@dataclass
class Mission:
    health: dict = field(default_factory=dict)
    enemies: dict = field(default_factory=dict)
    pickups: set = field(default_factory=set)
    checkpoint: str = ""
    finished: bool = False

class Session:
    def __init__(self):
        self.players = {}
        self.missions = {}
        self.next_id = 1
        self.campaign_level = None

    def send(self, player, line):
        writer = player['writer']
        # Disconnect slow readers rather than retain unbounded snapshot buffers.
        if writer.transport.get_write_buffer_size() > 65536:
            writer.close()
        elif not writer.is_closing():
            writer.write((line + '\n').encode('ascii'))

    def broadcast(self, line, level=None):
        for p in tuple(self.players.values()):
            if level is None or p['level'] == level:
                self.send(p, line)

    def mission(self, level):
        return self.missions.setdefault(level, Mission())

    def handle(self, p, line):
        parts = line.split()
        if not parts:
            raise ValueError('empty message')
        command, *args = parts
        if command == 'COAT' and len(args) == 1:
            slot = int(args[0])
            if not 0 <= slot < MAX_PLAYERS:
                raise ValueError('invalid coat')
            if any(q['id'] != p['id'] and q['slot'] == slot for q in self.players.values()):
                self.send(p, 'NOTICE That coat is in use; choose another color.')
            else:
                p['slot'] = slot
                self.broadcast(f"PLAYER {p['id']} {slot} {p['state']}")
                self.send(p, 'NOTICE Coat color selected.')
        elif command == 'START' and len(args) == 1:
            level = int(args[0])
            if not 1 <= level <= 13:
                raise ValueError('invalid mission')
            if p['id'] != min(self.players):
                self.send(p, 'NOTICE The host chooses the mission.')
            else:
                self.campaign_level = level
                print(f"Player {p['id']} started mission {level}", flush=True)
                self.missions[level] = Mission()
                self.broadcast(f'LOAD {level}')
        elif command == 'STATE' and len(args) == 5:
            level = int(args[0])
            x, y = map(float, args[1:3])
            if not (0 <= level <= 13 and all(math.isfinite(v) and abs(v) <= 1000000 for v in (x, y))
                    and args[3] in ('0', '1') and TOKEN.fullmatch(args[4])):
                raise ValueError('invalid state')
            changed = level != p['level']
            p['level'] = level
            p['state'] = ' '.join(args)
            self.broadcast(f"PLAYER {p['id']} {p['slot']} {p['state']}")
            if changed and level:
                m = self.mission(level)
                for key in sorted(m.pickups):
                    self.send(p, f'PICK {level} {key}')
                if m.checkpoint:
                    self.send(p, f'CHECK {level} {m.checkpoint}')
                if m.finished:
                    self.send(p, f'FINISH {level}')
        elif command in ('REG', 'DAMAGE', 'PICK', 'CHECK', 'FINISH', 'ENEMY'):
            if not args or int(args[0]) != p['level'] or p['level'] == 0:
                raise ValueError('join the mission first')
            level = p['level']
            m = self.mission(level)
            if command == 'ENEMY' and len(args) == 6:
                key = int(args[1])
                x, y = map(float, args[2:4])
                leader = min(q['id'] for q in self.players.values() if q['level'] == level)
                if p['id'] != leader:
                    return
                if key not in m.health or not all(math.isfinite(v) and abs(v) <= 1000000 for v in (x,y)) or args[4] not in ('0','1') or not TOKEN.fullmatch(args[5]):
                    raise ValueError('invalid enemy state')
                m.enemies[key] = ' '.join(args[2:])
                self.broadcast('ENEMY ' + ' '.join(args), level)
            elif command == 'REG' and len(args) == 3:
                key, health = int(args[1]), int(args[2])
                if not (0 <= key < 10000000 and 0 < health <= 1000000):
                    raise ValueError('invalid actor registration')
                m.health.setdefault(key, health)
                self.send(p, f'HEALTH {level} {key} {m.health[key]}')
            elif command == 'DAMAGE' and len(args) == 3:
                key, amount = int(args[1]), int(args[2])
                if key not in m.health or not (0 < amount <= 1000000):
                    raise ValueError('invalid damage')
                m.health[key] = max(0, m.health[key] - amount)
                self.broadcast(f'HEALTH {level} {key} {m.health[key]}', level)
            elif command == 'PICK' and len(args) == 2:
                key = int(args[1])
                if not 0 <= key < 10000000:
                    raise ValueError('invalid pickup')
                if key not in m.pickups:
                    m.pickups.add(key)
                    self.broadcast(f'PICK {level} {key}', level)
            elif command == 'CHECK' and len(args) == 5:
                x, y = map(float, args[1:3])
                if not all(math.isfinite(v) and abs(v) <= 1000000 for v in (x, y)) or args[3] not in ('0','1') or not 0 <= int(args[4]) <= 100:
                    raise ValueError('invalid checkpoint')
                m.checkpoint = ' '.join(args[1:])
                self.broadcast(f'CHECK {level} {m.checkpoint}', level)
            elif command == 'FINISH' and len(args) == 1:
                if not m.finished:
                    m.finished = True
                    self.broadcast(f'FINISH {level}', level)
            else:
                raise ValueError('invalid command')
        else:
            raise ValueError(f'unknown or incomplete command: {command} ({len(args)} arguments)')

    async def connect(self, reader, writer):
        p = None
        peer = writer.get_extra_info('peername')
        sock = writer.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        reason = 'left the session'
        try:
            hello = await asyncio.wait_for(reader.readline(), 5)
            if hello != b'HELLO 2\n':
                writer.write(b'ERROR protocol\n')
                return
            used = {p['slot'] for p in self.players.values()}
            slot = next((s for s in range(MAX_PLAYERS) if s not in used), None)
            if slot is None:
                writer.write(b'ERROR full\n')
                return
            p = dict(id=self.next_id, slot=slot, level=0, state='0 0 0 0 -', writer=writer)
            self.next_id += 1
            self.players[p['id']] = p
            self.send(p, f"WELCOME {p['id']} {slot}")
            for other in self.players.values():
                self.send(p, f"PLAYER {other['id']} {other['slot']} {other['state']}")
            if self.campaign_level is not None:
                self.send(p, f'LOAD {self.campaign_level}')
            print(f"Player {p['id']} joined from {peer}, coat {slot + 1}", flush=True)
            # Bounded input, finite inactivity timeout, and a per-client rate limit.
            window_start, messages = asyncio.get_running_loop().time(), 0
            while True:
                data = await asyncio.wait_for(reader.readline(), 120)
                if not data:
                    break
                if len(data) > MAX_LINE or not data.endswith(b'\n'):
                    raise ValueError('oversized message')
                now = asyncio.get_running_loop().time()
                if now - window_start >= 1:
                    window_start, messages = now, 0
                messages += 1
                if messages > 4000:
                    raise ValueError('rate limit')
                self.handle(p, data.decode('ascii').strip())
                await writer.drain()
        except (ValueError, UnicodeError, asyncio.TimeoutError, ConnectionError) as exc:
            reason = str(exc) or type(exc).__name__
        finally:
            if p:
                print(f"Player {p['id']} disconnected: {reason}", flush=True)
                self.players.pop(p['id'], None)
                self.broadcast(f"LEAVE {p['id']}")
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass
            # A completely empty session starts a fresh campaign on the next join.
            if not self.players:
                self.missions.clear()
                self.campaign_level = None

async def main(host, port):
    session = Session()
    server = await asyncio.start_server(session.connect, host, port, limit=MAX_LINE + 1)
    print(f'OpenClaw cooperative LAN server listening on {host}:{port} (8 players)', flush=True)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=27888)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
