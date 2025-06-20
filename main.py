from modules import SocketController, Logger
from socket import socket as socket_server
from threading import Thread
from config import HOST, PORT


def client_worker(l: Logger):
    sock = socket_server()
    l.info(f"Starting socket server on {HOST}:{PORT}")
    sock.bind((HOST, PORT))
    sock.listen(1)
    
    

if __name__ == "__main__":
    l = Logger()
    l.log("Starting")