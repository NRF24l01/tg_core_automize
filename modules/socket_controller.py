import asyncio
import json
from struct import pack, unpack
from socket import socket
from json import loads, dumps
from select import select
import threading


class SocketController:
    def __init__(self, socket: socket, logger=None):
        self.socket = socket
        self._send_lock = threading.Lock()
        self._read_lock = threading.Lock()

    def send_raw(self, raw: bytes):
        with self._send_lock:
            self.socket.send(pack("<I", len(raw)))
            self.socket.send(raw)

    def read_raw(self) -> bytes:
        with self._read_lock:
            len_unprocessed = b""
            while len(len_unprocessed) != 4:
                part = self.socket.recv(4 - len(len_unprocessed))
                len_unprocessed += part
            payload_len = unpack('<I', len_unprocessed)[0]
            payload = b""
            while len(payload) != payload_len:
                part = self.socket.recv(payload_len - len(payload))
                payload += part
        return payload

    def send_json(self, payload: dict | list):
        self.send_raw(dumps(payload).encode("UTF-8"))

    def data_avalible(self) -> bool:
        ready_to_read, _, _ = select([self.socket], [], [], 0)
        return bool(ready_to_read)

    def read_json(self, untill_packet: bool = False) -> dict | list | None:
        if not untill_packet:
            ready_to_read, _, _ = select([self.socket], [], [], 0)
            if not ready_to_read:
                return None
        raw = self.read_raw()
        return loads(raw.decode("UTF-8"))


class AsyncSocketController:
    def __init__(self, logger=None, reader: asyncio.StreamReader | None = None, writer: asyncio.StreamWriter | None = None):
        self.reader = reader
        self.writer = writer
        self._send_lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()
        self._buffer = bytearray()

    async def send_raw(self, raw: bytes):
        async with self._send_lock:
            length = pack("<I", len(raw))
            self.writer.write(length + raw)
            await self.writer.drain()

    async def _read_exactly(self, n: int) -> bytes:
        if len(self._buffer) >= n:
            result = self._buffer[:n]
            self._buffer = self._buffer[n:]
            return bytes(result)
        needed = n - len(self._buffer)
        data = await self.reader.readexactly(needed)
        result = self._buffer + data
        self._buffer.clear()
        return bytes(result)

    async def read_raw(self) -> bytes:
        async with self._read_lock:
            len_bytes = await self._read_exactly(4)
            payload_len = unpack("<I", len_bytes)[0]
            payload = await self._read_exactly(payload_len)
        return payload

    async def send_json(self, payload: dict | list):
        data = json.dumps(payload).encode("utf-8")
        await self.send_raw(data)

    async def read_json(self) -> dict | list:
        raw = await self.read_raw()
        return json.loads(raw.decode("utf-8"))

    async def data_available(self) -> bool:
        if self._buffer:
            return True
        try:
            data = await asyncio.wait_for(self.reader.read(1024), timeout=0.01)
            if data:
                self._buffer.extend(data)
                return True
            return False
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False
