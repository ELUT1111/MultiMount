import asyncio

import pytest

from app.adapters.ftp_adapter import FTPAdapter


class FakeFTP:
    def __init__(self):
        self.commands = []
        self.payload = b""
        self.passive_mode = None

    def set_pasv(self, value):
        self.passive_mode = value

    def storbinary(self, command, reader):
        self.commands.append(command)
        while True:
            chunk = reader.read(3)
            if not chunk:
                break
            self.payload += chunk


async def chunks():
    yield b"abc"
    await asyncio.sleep(0)
    yield b"defg"


@pytest.mark.asyncio
async def test_ftp_upload_reads_async_stream_from_worker_thread():
    ftp = FakeFTP()
    adapter = FTPAdapter("example.test", base_path="/home/user")
    adapter._ftp = ftp

    await adapter.upload("/target.txt", chunks())

    assert ftp.commands == ["STOR /home/user/target.txt"]
    assert ftp.payload == b"abcdefg"


@pytest.mark.asyncio
async def test_ftp_connect_applies_passive_mode(monkeypatch):
    created = []

    class ConnectFTP(FakeFTP):
        def connect(self, *_args, **_kwargs):
            return None

        def login(self, *_args, **_kwargs):
            return None

    def make_ftp():
        ftp = ConnectFTP()
        created.append(ftp)
        return ftp

    monkeypatch.setattr("ftplib.FTP", make_ftp)
    adapter = FTPAdapter("example.test", passive_mode=False)

    await adapter.connect()

    assert created[0].passive_mode is False
