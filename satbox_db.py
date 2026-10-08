"""Shared SQLite driver, with an optional fallback for custom Linux Python."""
try:
    import sqlite3
except ModuleNotFoundError as exc:
    if exc.name not in ('sqlite3','_sqlite3'):
        raise
    try:
        import pysqlite3 as sqlite3
    except ModuleNotFoundError as fallback:
        raise RuntimeError('SQLite support missing. On Xserver, install pysqlite3-binary==0.5.4.post2 in the virtual environment.') from fallback
