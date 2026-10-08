"""Fixed-source, validated and atomic NASA.ALL replacement; no orbit search."""
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from sgp4.api import Satrec
from satbox_orbit.catalog import read_catalog

SOURCE = 'https://www.amsat.org/tle/current/nasa.all'


class RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != 'https' or parsed.hostname not in ('www.amsat.org','amsat.org'):
            raise ValueError('Unexpected TLE redirect')
        return super().redirect_request(request,fp,code,msg,headers,newurl)


@contextmanager
def update_lock(folder):
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/'tle-update.lock').open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            if handle.tell() == 0:
                handle.write(b'0');handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def atomic_write(path,raw):
    fd,name = tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def update_catalog(config_path,private_dir,opener=None):
    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    target = config_path.parent/config['tle_file']
    metadata = config_path.parent/config['tle_metadata_file']
    with update_lock(Path(private_dir)):
        opener = opener or build_opener(RestrictedRedirect())
        with opener.open(Request(SOURCE,headers={'User-Agent':'SatBox-Cloud/0.1'}),timeout=10) as response:
            raw = response.read(2_000_001)
            modified = response.headers.get('Last-Modified')
        if len(raw) > 2_000_000:
            raise ValueError('TLE download too large')
        records = read_catalog(raw.decode('utf-8-sig'))
        if len({r.name.casefold() for r in records}) != len(records):
            raise ValueError('Duplicate satellite names')
        for record in records:
            if len(record.line1) < 68 or len(record.line2) < 68 or record.line1[2:7] != record.line2[2:7]:
                raise ValueError('Invalid TLE pair')
            model = Satrec.twoline2rv(record.line1,record.line2)
            if not model.satnum or not 0 < model.no_kozai < 1:
                raise ValueError('Invalid satellite model')
        now = datetime.now(timezone.utc)
        data = dict(source=SOURCE,saved_utc=now.isoformat(),last_modified=modified,
                    sha256=hashlib.sha256(raw).hexdigest(),satellite_count=len(records))
        backup = Path(private_dir)/'tle-backups'/now.strftime('%Y%m%dT%H%M%S%fZ')
        backup.mkdir(parents=True)
        if target.exists():(backup/'nasa.all').write_bytes(target.read_bytes())
        if metadata.exists():(backup/'metadata.json').write_bytes(metadata.read_bytes())
        atomic_write(metadata,(json.dumps(data,indent=2)+'\n').encode())
        atomic_write(target,raw)
        return len(records)
