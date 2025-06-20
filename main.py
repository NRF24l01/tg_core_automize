from modules import SocketController, Logger
from socket import socket as socket_server
import socket
from threading import Thread, Lock
from config import HOST, PORT

tasks = {}            # dict: ключ — имя клиента, значение — список задач
clients = set()       # set: имена клиентов

tasks_lock = Lock()
clients_lock = Lock()

def process_client(sock: socket_server, l: Logger):
    controller = SocketController(socket=sock)
    l.info("Start client processing")
    client_info = None
    while not client_info:
        client_info = controller.read_json()
    
    client_name = client_info["name"]
    with clients_lock:
        clients.add(client_name)
    client_required_events = client_info["required"]
    l.info(f"Client with name {client_name} requested events with id: {', '.join([str(i) for i in client_required_events])}")
    
    while True:
        if controller.data_avalible():
            data = controller.read_json()
            print("Received:", data)

        with tasks_lock:
            if client_name in tasks and len(tasks[client_name]) != 0:
                # Используем копию, чтобы безопасно удалять элементы
                new_task_list = []
                for task in tasks[client_name]:
                    if task["type"] in client_required_events:
                        controller.send_json(task)
                    else:
                        new_task_list.append(task)
                tasks[client_name] = new_task_list

def client_worker(l: Logger):
    sock = socket_server()
    l.info(f"Starting socket server on {HOST}:{PORT}")
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(1)
    
    l.info("Waiting for connections")
    while True:
        conn, addr = sock.accept()
        l.info(f"Connection from {addr}")
        t = Thread(target=process_client, args=(conn, l,), daemon=True)
        t.start()

def test_send():
    while True:
        i = input()
        if i == "":
            exit()
        with clients_lock:
            client_snapshot = list(clients)
        with tasks_lock:
            for client in client_snapshot:
                if client in tasks:
                    tasks[client].append({"type": 1, "message": i})
                else:
                    tasks[client] = [{"type": 1, "message": i}]

if __name__ == "__main__":
    l = Logger()
    l.info("Starting")
    t = Thread(target=test_send, daemon=True)
    t.start()
    
    client_worker(l)
