from __future__ import annotations
import grpc
import sys
import messages.tg_pb2 as tg_pb2
# register package module under the top-level name expected by generated code
sys.modules['tg_pb2'] = tg_pb2
import messages.tg_pb2_grpc as tg_pb2_grpc
from concurrent import futures
from typing import Iterator
import queue
import threading

class TgServiceImpl(tg_pb2_grpc.TgServiceServicer):
    def Exchange(self, request_iterator: Iterator[tg_pb2.TgMessage], context: grpc.ServicerContext) -> Iterator[tg_pb2.TgMessage]:
        # Используем очередь для исходящих сообщений (эти сообщения будут yield'иться)
        outgoing: "queue.Queue[object]" = queue.Queue()
        stop_sentinel = object()

        def handle_incoming():
            try:
                for msg in request_iterator:
                    print(f"[SERVER] Received: type={msg.type}, payload={dict(msg.payload)}")
                    # Эхо-ответ — кладём в очередь, чтобы он был отправлен клиенту
                    outgoing.put(tg_pb2.TgMessage(
                        type=msg.type,
                        is_private=msg.is_private,
                        config=msg.config,
                        payload={"server_echo": "Got your message!"},
                        direct=msg.direct,
                        target=msg.target,
                        module_name=msg.module_name
                    ))
            except Exception:
                # Игнорируем ошибки чтения входящего, просто завершаем
                pass
            finally:
                # Сигнализируем генератору о завершении входящего потока
                outgoing.put(stop_sentinel)

        def read_console():
            # Позволяем оператору сервера отправлять сообщения клиенту
            try:
                while context.is_active():
                    try:
                        text = input("SERVER> ")
                    except EOFError:
                        break
                    if not text:
                        continue
                    outgoing.put(tg_pb2.TgMessage(
                        type=tg_pb2.NEW_MESSAGE,
                        is_private=False,
                        payload={"text": text}
                    ))
            except Exception:
                # Игнорировать ошибки консоли
                pass
            finally:
                outgoing.put(stop_sentinel)

        # Запускаем потоки
        threading.Thread(target=handle_incoming, daemon=True).start()
        threading.Thread(target=read_console, daemon=True).start()

        # Начнём с приветственного сообщения (необязательно)
        outgoing.put(tg_pb2.TgMessage(
            type=tg_pb2.NEW_MESSAGE,
            is_private=True,
            payload={"server": "welcome"}
        ))

        # Генератор: отдаём сообщения из очереди пока не придёт sentinel или контекст не активен
        while context.is_active():
            item = outgoing.get()
            if item is stop_sentinel:
                # Попытка убедиться, что очередь опустела и завершить
                break
            yield item

def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    tg_pb2_grpc.add_TgServiceServicer_to_server(TgServiceImpl(), server)
    server.add_insecure_port("[::]:50051")
    print("[SERVER] Starting...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
