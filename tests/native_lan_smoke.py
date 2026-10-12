#!/usr/bin/env python3
"""Optional Linux/X11 smoke test using two real OpenClaw clients and original assets."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.lan_server import Session
from Scripts.play_lan import validate_archive
ROOT=Path(__file__).resolve().parents[1]

class AuditSession(Session):
    def __init__(self):
        super().__init__(); self.events=[]
    def handle(self,p,line):
        super().handle(p,line)
        if line.split()[0] in ('DAMAGE','PICK','CHECK','FINISH'):
            self.events.append((p['id'],line))

async def main():
    validate_archive(ROOT/'Build_Release/CLAW.REZ')
    output=ROOT/'artifacts/lan-smoke';output.mkdir(parents=True,exist_ok=True)
    xdotool=shutil.which('xdotool') or str(ROOT/'.local-deps/usr/bin/xdotool')
    env=os.environ.copy();env.update(DISPLAY=':100',SDL_RENDER_DRIVER='software',SDL_AUDIODRIVER='dummy')
    libs=ROOT/'.local-deps/usr/lib/x86_64-linux-gnu'
    if libs.is_dir(): env['LD_LIBRARY_PATH']=str(libs)+':'+env.get('LD_LIBRARY_PATH','')
    session=AuditSession()
    server=await asyncio.start_server(session.connect,'127.0.0.1',0,limit=513)
    env.update(OPENCLAW_SERVER='127.0.0.1',OPENCLAW_PORT=str(server.sockets[0].getsockname()[1]))
    processes=[];logs=[]
    xvfb=subprocess.Popen(['Xvfb',':100','-screen','0','1280x480x24'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    processes.append(xvfb)
    try:
        await asyncio.sleep(.5)
        with tempfile.TemporaryDirectory(prefix='openclaw-smoke-') as folder:
            for i in (1,2):
                cwd=Path(folder)/str(i);cwd.mkdir()
                for name in ('CLAW.REZ','ASSETS.ZIP','clacon.ttf','console02.tga'):
                    (cwd/name).symlink_to(ROOT/'Build_Release'/name)
                shutil.copy2(ROOT/'Build_Release/SAVES.XML',cwd/'SAVES.XML')
                config=ET.parse(ROOT/'Build_Release/config.xml');node=config.getroot()
                for path,value in [('DebugOptions/SkipMenu','true'),('DebugOptions/SkipMenuToLevel','1'),('DebugOptions/CpuDelay','10'),('Audio/SoundOn','false'),('Audio/MusicOn','false')]: node.find(path).text=value
                node.find('Display/Size').set('width','640');node.find('Display/Size').set('height','480')
                config.write(cwd/'config.xml')
                log=(output/f'client{i}.log').open('w');logs.append(log)
                game=subprocess.Popen([str(ROOT/'Build_Release/openclaw')],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
                processes.append(game)
                deadline=asyncio.get_running_loop().time()+15
                while len(session.players)<i or not all(p['level']==1 and p['state'].split()[-1]!='-' for p in session.players.values()):
                    if game.poll() is not None: raise AssertionError(f'Client {i} exited; see its log')
                    if asyncio.get_running_loop().time()>deadline: raise AssertionError('Mission did not load')
                    await asyncio.sleep(.1)
            async def xdo(*args):
                proc=await asyncio.create_subprocess_exec(xdotool,*map(str,args),env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                out,err=await proc.communicate()
                assert proc.returncode==0,err.decode()
                return out.decode().strip()
            windows=[]
            for i,game in enumerate(processes[1:]):
                window=(await xdo('search','--all','--pid',game.pid,'--name','Captain Claw')).splitlines()[0]
                windows.append(window);await xdo('windowmove',window,i*640,0)
            await asyncio.sleep(1)
            players=sorted(session.players.values(),key=lambda p:p['id'])
            start=[p['state'] for p in players]
            await xdo('keydown','--window',windows[0],'Right')
            await asyncio.sleep(.55)
            await xdo('keyup','--window',windows[0],'Right')
            await asyncio.sleep(1)
            assert float(players[0]['state'].split()[1])>float(start[0].split()[1])+100,'Player did not move'
            assert abs(float(players[1]['state'].split()[1])-float(start[1].split()[1]))<5,'Other player moved unexpectedly'
            await xdo('windowraise',windows[0])
            capture=await asyncio.create_subprocess_exec('import','-window',windows[0],str(output/'cooperative-coats.png'),env=env)
            await capture.wait()
            # Walk and attack until contact destroys a crate, rather than
            # relying on one exact frame-dependent movement duration.
            await xdo('keydown','--window',windows[0],'Right')
            deadline=asyncio.get_running_loop().time()+4
            while not any(hp==0 for hp in session.missions[1].health.values()):
                await xdo('key','--window',windows[0],'Control_L')
                await asyncio.sleep(.15)
                if asyncio.get_running_loop().time()>deadline: break
            await asyncio.sleep(.4)
            await xdo('keyup','--window',windows[0],'Right')
            await asyncio.sleep(2)
            await xdo('windowraise',windows[0])
            capture=await asyncio.create_subprocess_exec('import','-window',windows[0],str(output/'cooperative-level1.png'),env=env)
            await capture.wait()
            # A third real client must reconstruct a destroyed crate and its
            # already-collected loot, even though pickup history arrives first.
            late_cwd=Path(folder)/'3';late_cwd.mkdir()
            for name in ('CLAW.REZ','ASSETS.ZIP','clacon.ttf','console02.tga'):
                (late_cwd/name).symlink_to(ROOT/'Build_Release'/name)
            shutil.copy2(ROOT/'Build_Release/SAVES.XML',late_cwd/'SAVES.XML')
            shutil.copy2(Path(folder)/'1/config.xml',late_cwd/'config.xml')
            late_log=(output/'client3.log').open('w');logs.append(late_log)
            late_game=subprocess.Popen([str(ROOT/'Build_Release/openclaw')],cwd=late_cwd,env=env,stdout=late_log,stderr=subprocess.STDOUT)
            processes.append(late_game)
            deadline=asyncio.get_running_loop().time()+15
            while 'LAN: shared pickup ' not in (output/'client3.log').read_text():
                if late_game.poll() is not None: raise AssertionError('Late joiner exited')
                if asyncio.get_running_loop().time()>deadline: raise AssertionError('Late joiner did not reconstruct collected loot')
                await asyncio.sleep(.1)
            assert 'LAN: actor ' in (output/'client3.log').read_text(),'Late joiner did not reconstruct destroyed actors'
            session.handle(players[0],'CHECK 1 689 4735 1 1')
            await asyncio.sleep(.5)
            session.handle(players[0],'FINISH 1')
            deadline=asyncio.get_running_loop().time()+10
            while any(p['level']!=0 for p in players):
                if any(p.poll() is not None for p in processes[1:]): raise AssertionError('Client exited during mission completion')
                if asyncio.get_running_loop().time()>deadline: raise AssertionError('Score screens did not load on both clients')
                await asyncio.sleep(.1)
            summary={'players':len(session.players),'coat_slots':[p['slot'] for p in players],
                'late_join_replayed':True,'initial_states':start,'final_states':[p['state'] for p in players],
                'registered_health_actors':len(session.missions[1].health),
                'dead_actors':sum(hp==0 for hp in session.missions[1].health.values()),
                'shared_pickups':len(session.missions[1].pickups),'shared_checkpoint':session.missions[1].checkpoint,'mission_finished':session.missions[1].finished,'events':session.events}
            (output/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
            print(json.dumps(summary,indent=2))
            assert summary['dead_actors']>0,'Melee did not destroy a shared crate'
            assert summary['shared_pickups']>0,'No shared loot was collected'
            for i in (1,2,3):
                text=(output/f'client{i}.log').read_text()
                assert 'LAN: actor ' in text and 'LAN: shared pickup ' in text,f'Client {i} did not apply shared damage and loot'
                assert 'Assertion' not in text and 'LAN connection closed' not in text,f'Client {i} failed'
    finally:
        for p in reversed(processes):
            if p.poll() is None: p.terminate()
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired: p.kill();p.wait()
        for log in logs: log.close()
        server.close();await server.wait_closed()

if __name__=='__main__': asyncio.run(main())
