from modules import SocketController, Logger
from socket import socket as socket_server
from threading import Thread
from config import HOST, PORT



def process_client(sock: socket_server, l: Logger):
    controller = SocketController(socket=sock)
    l.info("Start client processing")
    client_info = None
    while not client_info:
        client_info = controller.read_json()
    
    client_name = client_info["name"]
    client_required_events = client_info["required"]
    l.info(f"Client with name {client_name} requested events with id: {', '.join(client_required_events)}")

def client_worker(l: Logger):
    sock = socket_server()
    l.info(f"Starting socket server on {HOST}:{PORT}")
    sock.bind((HOST, PORT))
    sock.listen(1)
    
    l.info("Waiting for connections")
    while True:
        conn, addr = sock.accept()
        l.info(f"Connection from {addr}")
        t = Thread(target=process_client, args=(conn, l))
        t.start()
        
    

if __name__ == "__main__":
    l = Logger()
    l.log("Starting")