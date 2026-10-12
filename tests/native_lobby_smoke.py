#!/usr/bin/env python3
"""Exercise Host, Join, coats and mission launch with three native game clients."""
import asyncio
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from Scripts.play_lan import validate_archive

async def main():
    validate_archive(ROOT/'Build_Release/CLAW.REZ')
    output=ROOT/'artifacts/lobby-smoke';output.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    env=os.environ.copy();env.pop('OPENCLAW_SERVER',None)
    env.update(DISPLAY=':101',SDL_RENDER_DRIVER='software',SDL_AUDIODRIVER='dummy',OPENCLAW_PORT=str(port))
    libs=ROOT/'.local-deps/usr/lib/x86_64-linux-gnu'
    if libs.is_dir(): env['LD_LIBRARY_PATH']=str(libs)+':'+env.get('LD_LIBRARY_PATH','')
    xdotool=shutil.which('xdotool') or str(ROOT/'.local-deps/usr/bin/xdotool')
    xvfb=subprocess.Popen(['Xvfb',':101','-screen','0','1920x480x24'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    games=[];logs=[];windows=[]
    async def xdo(*args):
        process=await asyncio.create_subprocess_exec(xdotool,*map(str,args),env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        out,err=await process.communicate()
        assert process.returncode==0,err.decode()
        return out.decode().strip()
    async def wait_for(predicate,message,timeout=15):
        deadline=asyncio.get_running_loop().time()+timeout
        while not predicate():
            assert all(p.poll() is None for p in games),f'Game exited: {message}'
            if asyncio.get_running_loop().time()>deadline: raise AssertionError(message)
            await asyncio.sleep(.1)
    async def capture(window,name):
        await xdo('windowraise',window)
        process=await asyncio.create_subprocess_exec('import','-window',window,str(output/name),env=env)
        assert await process.wait()==0
    try:
        await asyncio.sleep(.5)
        with tempfile.TemporaryDirectory(prefix='openclaw-lobby-') as temp:
            for i in range(3):
                cwd=Path(temp)/str(i);cwd.mkdir()
                for name in ('CLAW.REZ','ASSETS.ZIP','clacon.ttf','console02.tga'):
                    (cwd/name).symlink_to(ROOT/'Build_Release'/name)
                shutil.copy2(ROOT/'Build_Release/SAVES.XML',cwd/'SAVES.XML')
                config=ET.parse(ROOT/'Build_Release/config.xml');node=config.getroot()
                for path,value in [('DebugOptions/SkipMenu','false'),('DebugOptions/CpuDelay','5'),('Audio/SoundOn','false'),('Audio/MusicOn','false')]: node.find(path).text=value
                node.find('Display/Size').set('width','640');node.find('Display/Size').set('height','480')
                config.write(cwd/'config.xml')
                log=(output/f'client{i+1}.log').open('w');logs.append(log)
                game=subprocess.Popen([str(ROOT/'Build_Release/openclaw')],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT);games.append(game)
                path=output/f'client{i+1}.log'
                await wait_for(lambda:'Changing to: 3' in path.read_text(),'Main menu did not load')
                window=(await xdo('search','--all','--pid',game.pid,'--name','Captain Claw')).splitlines()[0]
                windows.append(window);await xdo('windowmove',window,i*640,0)
                await xdo('windowfocus',window)
                await xdo('key','--window',window,'m');await asyncio.sleep(.15)
                if i==0:
                    await capture(window,'host-join-menu.png')
                    await xdo('key','--window',window,'h')
                else:
                    await xdo('key','--window',window,'j');await asyncio.sleep(.1)
                    for _ in range(i): await xdo('key','--window',window,'Right')
                    await xdo('key','--window',window,'Return')
                await wait_for(lambda:'LAN: connected' in path.read_text(),'Host/Join did not connect')
            await asyncio.sleep(.4)
            # The host must be able to cycle past colors reserved by other
            # players, select a free color, and switch back to red.
            for key in ('Right','Right','Right'):
                await xdo('key','--window',windows[0],key);await asyncio.sleep(.12)
            await capture(windows[0],'coat-selection.png')
            assert 'LAN: coat changed to 4' in (output/'client1.log').read_text(),'Could not cycle past reserved coats'
            for key in ('Left','Left','Left'):
                await xdo('key','--window',windows[0],key);await asyncio.sleep(.12)
            await capture(windows[0],'three-player-lobby.png')
            assert 'LAN: coat changed to 1' in (output/'client1.log').read_text(),'Could not restore the red coat'
            await xdo('key','--window',windows[0],'Return')
            for i in range(3):
                path=output/f'client{i+1}.log'
                await wait_for(lambda:'Level loaded !' in path.read_text(),'Shared mission did not load')
            await asyncio.sleep(1)
            # Separate all three players so each avatar is visibly distinguishable.
            for i,duration in [(1,.12),(2,.25)]:
                await xdo('keydown','--window',windows[i],'Right');await asyncio.sleep(duration)
                await xdo('keyup','--window',windows[i],'Right')
            await asyncio.sleep(.5)
            for i in range(3):
                path=output/f'client{i+1}.log'
                await wait_for(lambda:len(set(re.findall(r'rendering remote player (\d+)',path.read_text())))==2,'A client failed to render both remote players')
            await capture(windows[0],'three-player-coats.png')
            # Keep three active clients alive while actions and snapshots continue.
            for _ in range(3):
                for i in (1,2):
                    await xdo('keydown','--window',windows[i],'space')
                await asyncio.sleep(.25)
                for i in (1,2): await xdo('keyup','--window',windows[i],'space')
                await asyncio.sleep(.6)
            results=[]
            for i in range(3):
                text=(output/f'client{i+1}.log').read_text()
                assert 'Assertion' not in text and 'disconnected:' not in text,'Native client disconnected or crashed'
                assert 'Could not switch to page: MenuPage_Multiplayer' not in text,'Multiplayer menu is still broken'
                rendered=sorted(set(re.findall(r'rendering remote player (\d+) coat (\d+)',text)))
                results.append({'player':i+1,'remote_players_rendered':rendered})
            (output/'result.json').write_text(json.dumps(results,indent=2)+'\n')
            print(json.dumps(results,indent=2))
    finally:
        for game in reversed(games):
            if game.poll() is None: game.terminate()
            try: game.wait(timeout=5)
            except subprocess.TimeoutExpired: game.kill();game.wait()
        for log in logs: log.close()
        xvfb.terminate();xvfb.wait(timeout=5)

if __name__=='__main__': asyncio.run(main())
