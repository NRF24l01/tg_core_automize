from modules import SocketController
from socket import socket as client_socket
from config import HOST, PORT
from threading import Thread

sock = client_socket()
sock.connect((HOST, PORT))
controller = SocketController(sock)

controller.send_json({"name": "parrot", "required": [1,2,3,4]})

def test_send(sock: SocketController):
    while True:
        i = input()
        if i == "":
            exit()
        sock.send_json({"type": 1, "payload": i})
        
        

t = Thread(target=test_send, args=(controller,))
t.start()

while True:
    print(controller.read_json(untill_packet=True))
