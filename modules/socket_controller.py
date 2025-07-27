import asyncio
from struct import pack, unpack
from json import loads, dumps


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
        data = dumps(payload).encode("utf-8")
        await self.send_raw(data)

    async def read_json(self) -> dict | list:
        raw = await self.read_raw()
        return loads(raw.decode("utf-8"))

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
