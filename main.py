from modules import SocketController, Logger
from socket import socket as socket_server
from threading import Thread
from config import HOST, PORT

tasks = {} # dict, keys - client ids, contains fully prepaired messages for client
clients = set() # list with clients names

def process_client(sock: socket_server, l: Logger):
    controller = SocketController(socket=sock)
    l.info("Start client processing")
    client_info = None
    while not client_info:
        client_info = controller.read_json()
    
    client_name = client_info["name"]
    clients.add(client_name)
    client_required_events = client_info["required"]
    l.info(f"Client with name {client_name} requested events with id: {', '.join([str(i) for i in client_required_events])}")
    
    data = None
    while True:
        if controller.data_avalible():
            data = controller.read_json()
            print("Recived:", data)
        if client_name in tasks.keys() and len(tasks[client_name]) != 0:
            for i, task in enumerate(tasks[client_name]):
                print(task)
                if task["type"] in client_required_events:
                    controller.send_json(task)
                tasks[client_name].pop(i)

def client_worker(l: Logger):
    sock = socket_server()
    l.info(f"Starting socket server on {HOST}:{PORT}")
    sock.bind((HOST, PORT))
    sock.listen(1)
    
    l.info("Waiting for connections")
    while True:
        conn, addr = sock.accept()
        l.info(f"Connection from {addr}")
        t = Thread(target=process_client, args=(conn, l, ))
        t.start()
        
def test_send():
    while True:
        i = input()
        if i == "":
            exit()
        for client in clients:
            if client in tasks.keys():
                tasks[client].append({"type": 1, "message": i})
            else:
                tasks[client] = [{"type": 1, "message": i}]

if __name__ == "__main__":
    l = Logger()
    l.info("Starting")
    t = Thread(target=test_send)
    t.start()
    
    client_worker(l)