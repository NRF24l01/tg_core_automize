from __future__ import annotations
import grpc
import threading
from typing import Iterator
import sys
import messages.tg_pb2 as tg_pb2
# register package module under the top-level name expected by generated code
sys.modules['tg_pb2'] = tg_pb2
import messages.tg_pb2_grpc as tg_pb2_grpc

def send_messages() -> Iterator[tg_pb2.TgMessage]:
    while True:
        text = input("> ")
        if not text:
            continue
        yield tg_pb2.TgMessage(
            type=tg_pb2.NEW_MESSAGE,
            is_private=False,
            payload={"text": text}
        )

def run_client() -> None:
    channel = grpc.insecure_channel("localhost:50051")
    stub = tg_pb2_grpc.TgServiceStub(channel)

    def receiver():
        for resp in stub.Exchange(send_messages()):
            print(f"[CLIENT] Received from server: payload={dict(resp.payload)}")

    receiver_thread = threading.Thread(target=receiver, daemon=True)
    receiver_thread.start()

    # Блокируем основной поток, чтобы input работал
    receiver_thread.join()

if __name__ == "__main__":
    run_client()
