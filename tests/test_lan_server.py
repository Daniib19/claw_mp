import asyncio
import unittest
from server.lan_server import Session

class LanServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = Session()
        self.server = await asyncio.start_server(self.session.connect, '127.0.0.1', 0, limit=513)
        self.port = self.server.sockets[0].getsockname()[1]
        self.clients = []

    async def asyncTearDown(self):
        for r, w in self.clients:
            w.close()
        for r, w in self.clients:
            await w.wait_closed()
        self.server.close()
        await self.server.wait_closed()
        await asyncio.sleep(0)

    async def connect(self):
        r, w = await asyncio.open_connection('127.0.0.1', self.port)
        self.clients.append((r,w))
        w.write(b'HELLO 2\n'); await w.drain()
        line = (await asyncio.wait_for(r.readline(), 1)).decode().strip()
        return r,w,line

    async def send(self, client, line):
        client[1].write((line+'\n').encode()); await client[1].drain()

    async def expect(self, client, expected):
        async def read():
            while True:
                line=(await client[0].readline()).decode().strip()
                if not line:
                    self.fail(f'connection closed waiting for {expected}')
                if line == expected:
                    return line
        return await asyncio.wait_for(read(), 1)

    async def join_level(self, client, level=1):
        await self.send(client, f'STATE {level} 100 200 0 frame001.pid')
        await self.expect(client, f"PLAYER {client[2].split()[1]} {client[2].split()[2]} {level} 100 200 0 frame001.pid")

    async def test_distinct_coats_and_capacity(self):
        clients=[await self.connect() for _ in range(8)]
        self.assertEqual({int(c[2].split()[2]) for c in clients},set(range(8)))
        rejected=await self.connect()
        self.assertEqual(rejected[2],'ERROR full')

    async def test_shared_damage_pickups_checkpoint_and_completion(self):
        a,b=await self.connect(),await self.connect()
        await self.join_level(a); await self.join_level(b)
        await self.send(a,'REG 1 9 100'); await self.expect(a,'HEALTH 1 9 100')
        await self.send(b,'REG 1 9 100'); await self.expect(b,'HEALTH 1 9 100')
        await self.send(a,'DAMAGE 1 9 30'); await self.send(b,'DAMAGE 1 9 40')
        await self.expect(a,'HEALTH 1 9 30'); await self.expect(b,'HEALTH 1 9 30')
        await self.send(a,'PICK 1 12'); await self.send(b,'PICK 1 12')
        await self.expect(a,'PICK 1 12'); await self.expect(b,'PICK 1 12')
        self.assertEqual(self.session.missions[1].pickups,{12})
        await self.send(a,'CHECK 1 300 400 1 2')
        await self.expect(b,'CHECK 1 300 400 1 2')
        await self.send(b,'FINISH 1'); await self.expect(a,'FINISH 1')
        c=await self.connect(); await self.join_level(c)
        await self.expect(c,'PICK 1 12'); await self.expect(c,'CHECK 1 300 400 1 2'); await self.expect(c,'FINISH 1')
        await self.send(c,'REG 1 9 100'); await self.expect(c,'HEALTH 1 9 30')

    async def test_damage_clamped_and_health_not_reset_by_joiner(self):
        a=await self.connect(); await self.join_level(a)
        await self.send(a,'REG 1 1 10'); await self.expect(a,'HEALTH 1 1 10')
        await self.send(a,'DAMAGE 1 1 100'); await self.expect(a,'HEALTH 1 1 0')
        await self.send(a,'REG 1 1 100'); await self.expect(a,'HEALTH 1 1 0')

    async def test_enemy_leader_and_transfer(self):
        a,b=await self.connect(),await self.connect()
        await self.join_level(a); await self.join_level(b)
        await self.send(a,'REG 1 4 10'); await self.expect(a,'HEALTH 1 4 10')
        await self.send(b,'ENEMY 1 4 1 2 0 frame001.pid')
        await self.send(a,'ENEMY 1 4 10 20 1 frame002.pid')
        await self.expect(b,'ENEMY 1 4 10 20 1 frame002.pid')
        a[1].close(); await a[1].wait_closed()
        await self.expect(b,'LEAVE 1')
        await self.send(b,'ENEMY 1 4 30 40 0 frame003.pid')
        await self.expect(b,'ENEMY 1 4 30 40 0 frame003.pid')
        self.assertEqual(self.session.missions[1].enemies[4],'30 40 0 frame003.pid')
        c=await self.connect(); self.assertEqual(c[2],'WELCOME 3 0')

    async def test_different_missions_are_isolated(self):
        a,b=await self.connect(),await self.connect()
        await self.join_level(a,1); await self.join_level(b,2)
        await self.send(a,'REG 1 1 50'); await self.expect(a,'HEALTH 1 1 50')
        await self.send(b,'REG 2 1 100'); await self.expect(b,'HEALTH 2 1 100')
        await self.send(a,'DAMAGE 1 1 20'); await self.expect(a,'HEALTH 1 1 30')
        self.assertEqual(self.session.missions[2].health[1],100)

    async def test_malformed_and_oversized_messages_disconnect(self):
        for line in ['STATE 1 nan 0 0 frame001.pid','STATE 99 0 0 0 -','DAMAGE 1 2 -5','X'*600]:
            client=await self.connect()
            await self.send(client,line)
            async def eof():
                while await client[0].readline(): pass
            await asyncio.wait_for(eof(),1)

    async def test_lobby_mission_start_coats_and_late_join(self):
        a,b,c=await self.connect(),await self.connect(),await self.connect()
        await self.send(c,'COAT 5')
        await self.expect(a,'PLAYER 3 5 0 0 0 0 -')
        await self.send(b,'COAT 5')
        await self.expect(b,'NOTICE That coat is in use; choose another color.')
        self.assertEqual(self.session.players[2]['slot'],1)
        await self.send(b,'START 3')
        await self.expect(b,'NOTICE The host chooses the mission.')
        self.assertIsNone(self.session.campaign_level)
        await self.send(a,'START 3')
        for client in (a,b,c): await self.expect(client,'LOAD 3')
        late=await self.connect(); await self.expect(late,'LOAD 3')
        self.assertEqual(len({p['slot'] for p in self.session.players.values()}),4)

    async def test_three_players_sustained_snapshot_stream(self):
        clients=[await self.connect() for _ in range(3)]
        for c in clients: await self.join_level(c)
        async def write_frames(c):
            for n in range(60):
                await self.send(c,f'STATE {1} 999 {n} 0 frame001.pid')
                await asyncio.sleep(1/60)
        # Distinguish samples by Y, with all three players in mission 1.
        async def read_frames(c):
            seen=set()
            while len(seen)<180:
                fields=(await c[0].readline()).decode().strip().split()
                self.assertTrue(fields,'player disconnected')
                if fields[0]=='PLAYER' and fields[4]=='999': seen.add((int(fields[1]),int(fields[5])))
            return seen
        readers=[asyncio.create_task(read_frames(c)) for c in clients]
        await asyncio.gather(*(write_frames(c) for c in clients))
        results=await asyncio.wait_for(asyncio.gather(*readers),2)
        self.assertTrue(all(len(seen)==180 for seen in results))
        self.assertEqual(len(self.session.players),3)

    async def test_protocol_version(self):
        r,w=await asyncio.open_connection('127.0.0.1',self.port)
        self.clients.append((r,w)); w.write(b'HELLO 1\n'); await w.drain()
        self.assertEqual(await r.readline(),b'ERROR protocol\n')

if __name__=='__main__': unittest.main()
