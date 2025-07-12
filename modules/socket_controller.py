import asyncio
import json
from struct import pack, unpack
from socket import socket
from json import loads, dumps
from select import select


class SocketController:
    def __init__(self, socket: socket):
        self.socket = socket
        
    def send_raw(self, raw: bytes):
        self.socket.send(pack("<I", len(raw)))
        self.socket.send(raw)
    
    def read_raw(self) -> bytes:
        len_unprocessed = b""
        while len(len_unprocessed) != 4:
            len_unprocessed += self.socket.recv(4-len(len_unprocessed))
        payload_len = int(unpack('<I', len_unprocessed)[0])
        payload = b""
        while len(payload) != payload_len:
            payload += self.socket.recv(payload_len-len(payload))
        return payload
    
    def send_json(self, payload: dict | list):
        self.send_raw(dumps(payload).encode("UTF-8"))
    
    def data_avalible(self) -> bool:
        ready_to_read, _, _ = select([self.socket], [], [], 0)
        if not ready_to_read:
            return False
        return True
    
    def read_json(self, untill_packet: bool = False) -> dict | list | None:
        if not untill_packet:
            ready_to_read, _, _ = select([self.socket], [], [], 0)
            if not ready_to_read:
                return None
        
        return loads(self.read_raw().decode("UTF-8"))
    

class AsyncSocketController:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._buffer = bytearray()  # внутренний буфер для данных, которые прочитали, но ещё не обработали

    async def send_raw(self, raw: bytes):
        length = pack("<I", len(raw))
        self.writer.write(length + raw)
        await self.writer.drain()

    async def _read_exactly(self, n: int) -> bytes:
        # Сначала пытаемся взять из буфера
        if len(self._buffer) >= n:
            result = self._buffer[:n]
            self._buffer = self._buffer[n:]
            return bytes(result)

        # Если в буфере недостаточно — докачиваем с ридера
        needed = n - len(self._buffer)
        data = await self.reader.readexactly(needed)
        result = self._buffer + data
        self._buffer.clear()
        return bytes(result)

    async def read_raw(self) -> bytes:
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
        # Проверяем есть ли уже данные в буфере
        if self._buffer:
            return True
        
        # Попробуем неблокирующе прочитать данные (если есть) с помощью wait_for с 0.01 сек
        try:
            data = await asyncio.wait_for(self.reader.read(1024), timeout=0.01)
            if data:
                self._buffer.extend(data)
                return True
            return False
        except asyncio.TimeoutError:
            return False
