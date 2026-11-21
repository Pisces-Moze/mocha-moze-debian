#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Minimal newc reader/writer preserving file types, links and ownership."""
import gzip


def read_newc(blob):
    offset=0;entries=[]
    while True:
        header=blob[offset:offset+110]
        if len(header)!=110 or header[:6]!=b'070701':raise ValueError('Expected newc archive')
        fields=[int(header[i:i+8],16) for i in range(6,110,8)]
        namesize=fields[11];size=fields[6]
        if not 0<namesize<=4096 or size>256*1024**2:raise ValueError('Invalid RAM entry size')
        start=offset+110
        rawname=blob[start:start+namesize]
        if not rawname.endswith(b'\0'):raise ValueError('Invalid cpio name')
        name=rawname[:-1].decode('utf-8')
        if name.startswith('./'):name=name[2:]
        if name.startswith('/') or '..' in name.split('/'):raise ValueError('Unsafe RAM path')
        start=(start+namesize+3)&~3
        data=blob[start:start+size]
        if len(data)!=size:raise ValueError('Truncated RAM entry')
        offset=(start+size+3)&~3
        if name=='TRAILER!!!':return entries
        entries.append((name,fields,data))


def write_newc(entries):
    result=bytearray()
    for name,fields,data in entries+[('TRAILER!!!',[0]*13,b'')]:
        encoded=name.encode()+b'\0';values=list(fields)
        values[6]=len(data);values[11]=len(encoded)
        result.extend(b'070701'+b''.join(f'{v:08x}'.encode() for v in values))
        result.extend(encoded);result.extend(b'\0'*((-len(result))%4))
        result.extend(data);result.extend(b'\0'*((-len(result))%4))
    result.extend(b'\0'*((-len(result))%512))
    return bytes(result)


def regular(name,data,mode=0o100600,ino=0):
    fields=[ino,mode,0,0,1,0,len(data),0,0,0,0,0,0]
    return name,fields,data


def personalize(source,destination,public_key):
    if not public_key.startswith(b'ssh-ed25519 ') or b'\n' in public_key.strip() or len(public_key)>256:
        raise ValueError('One Ed25519 public key required')
    entries=read_newc(gzip.decompress(source.read_bytes()))
    matches=[index for index,(name,_,_) in enumerate(entries) if name=='root/.ssh/authorized_keys']
    if len(matches)!=1:raise ValueError('Expected one installer key placeholder')
    name,fields,_=entries[matches[0]]
    entries[matches[0]]=(name,fields,public_key.strip()+b'\n')
    destination.write_bytes(gzip.compress(write_newc(entries),compresslevel=6,mtime=0))
