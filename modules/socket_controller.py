from socket import socket
from json import loads, dumps
from struct import pack, unpack
from select import select


class SocketController:
    def __init__(self, socket: socket):
        self.socket = socket
        
    def send_raw(self, raw: bytes):
        self.socket.send(pack("<I", len(raw)))
        self.socket.send(raw)
    
    def read_raw(self) -> bytes | None:
        ready_to_read, _, _ = select([self.socket], [], [], 0)
        if not ready_to_read:
            return None
        
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
    
    def read_json(self) -> dict | list | None:
        ready_to_read, _, _ = select([self.socket], [], [], 0)
        if not ready_to_read:
            return None
        
        return loads(self.read_raw().decode("UTF-8"))
