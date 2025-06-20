from modules import SocketController, Logger
from socket import socket as socket_server
import socket
from threading import Thread, Lock
from queue import Queue, Empty
from config import HOST, PORT

tasks = {}            # dict[str, Queue]: очередь задач для каждого клиента
clients = set()       # set: имена клиентов
clients_lock = Lock()

def process_client(sock: socket_server, l: Logger):
    controller = SocketController(socket=sock)
    l.info("Start client processing")
    
    client_info = None
    while not client_info:
        client_info = controller.read_json()
    
    client_name = client_info["name"]
    client_required_events = client_info["required"]

    with clients_lock:
        clients.add(client_name)
        if client_name not in tasks:
            tasks[client_name] = Queue()

    l.info(f"Client '{client_name}' requested events with id: {', '.join(map(str, client_required_events))}")
    
    while True:
        if controller.data_avalible():
            data = controller.read_json()
            print("Received:", data)
        
        # Отправляем задачи из очереди
        q = tasks[client_name]
        try:
            while True:  # Выгружаем все подходящие задачи
                task = q.get_nowait()
                if task["type"] in client_required_events:
                    controller.send_json(task)
                else:
                    q.put(task)  # возвращаем в очередь, если тип не подходит
                    break
        except Empty:
            pass

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
        t = Thread(target=process_client, args=(conn, l), daemon=True)
        t.start()

def test_send():
    while True:
        i = input()
        if i == "":
            exit()
        with clients_lock:
            for client in clients:
                if client not in tasks:
                    tasks[client] = Queue()
                tasks[client].put({"type": 1, "message": i})

if __name__ == "__main__":
    l = Logger()
    l.info("Starting")
    t = Thread(target=test_send, daemon=True)
    t.start()

    client_worker(l)
