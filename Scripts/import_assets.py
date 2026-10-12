#!/usr/bin/env python3
"""Pack a Captain Claw installation's loose Assets into an OpenClaw REZ archive."""
import argparse
from pathlib import Path
import re
import shutil
import struct
import tempfile


def pack_assets(assets, destination, header_source=None):
    assets, destination = Path(assets), Path(destination)
    required=['CLAW/IMAGES/FRAME001.PID','LEVEL1/WORLDS/WORLD.WWD','STATES/MENU/SCREENS/MENU.PCX']
    files=sorted((p for p in assets.rglob('*') if p.is_file()),key=lambda p:str(p.relative_to(assets)).lower())
    lookup={p.relative_to(assets).as_posix().upper():p for p in files}
    missing=[name for name in required if name not in lookup]
    if missing:
        raise ValueError('Missing original game assets: '+', '.join(missing))
    header=bytearray(168)
    if header_source and Path(header_source).is_file():
        with Path(header_source).open('rb') as f: header[:127]=f.read(127)
    if not any(header[:127]):
        text=b'\r\nOpenClaw local asset archive\r\n'
        header[:len(text)]=text
    struct.pack_into('<I',header,127,1)
    tree={}
    seen=set()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent,suffix='.rez.tmp',delete=False) as out:
        temp=Path(out.name)
        try:
            out.write(header)
            for p in files:
                rel=p.relative_to(assets)
                # REZ extensions occupy four bytes, including the trailing zero.
                ext=p.suffix[1:]
                if not ext or len(ext)>3:
                    continue
                name=p.stem
                normalized=rel.as_posix().lower()
                if normalized in seen: raise ValueError(f'Duplicate case-insensitive path: {rel}')
                seen.add(normalized)
                node=tree
                for part in rel.parts[:-1]: node=node.setdefault(part.lower(),{})
                offset=out.tell()
                with p.open('rb') as source: shutil.copyfileobj(source,out)
                size=out.tell()-offset
                number=re.search(r'(\d+)$',name)
                file_id=int(number.group(1)) if number else 0
                encoded_ext=ext[::-1].upper().encode('ascii').ljust(4,b'\0')
                entry=struct.pack('<IIIII',0,offset,size,0,file_id)+encoded_ext+struct.pack('<I',0)+name.encode('ascii')+b'\0\0'
                node[name.lower()+'.'+ext.lower()]=entry

            def write_directory(node):
                entries=[]
                for name, value in sorted(node.items()):
                    if isinstance(value,dict):
                        offset,size=write_directory(value)
                        entries.append(struct.pack('<IIII',1,offset,size,0)+name.encode('ascii')+b'\0')
                    else: entries.append(value)
                offset=out.tell()
                for entry in entries: out.write(entry)
                return offset,out.tell()-offset
            offset,size=write_directory(tree)
            out.seek(131); out.write(struct.pack('<II',offset,size))
            out.flush()
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    temp.replace(destination)
    return len(seen)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installation',type=Path)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'Build_Release/CLAW.REZ')
    args=parser.parse_args()
    try:
        count=pack_assets(args.installation/'Assets',args.output,args.installation/'CLAW.REZ')
    except (ValueError,OSError) as exc: parser.error(str(exc))
    print(f'Packed {count} files into {args.output} ({args.output.stat().st_size:,} bytes).')
