import sys
from datetime import datetime
from typing import TextIO


def debug(message: str):
    _print("DEBUG", message)


def info(message: str):
    _print("INFO", message)


def warning(message: str):
    _print("WARN", message, file=sys.stderr)


def error(message: str):
    _print("ERROR", message, file=sys.stderr)


def request(uid: str, message: str):
    _print("REQUEST", f"[{uid}] {message}")


def _print(level: str, message: str, file: TextIO = sys.stdout):
    now: datetime = datetime.now()
    date = f"{now.month}/{now.day}"
    time = f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"
    message = f"[{level}] {date} {time} >> {message}"
    print(message, file=file, flush=True)
