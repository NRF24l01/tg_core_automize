# Static files regen

- From root directory, run
```shell
python -m grpc_tools.protoc \                                                               
    -I . \
    --python_out=. \
    --grpc_python_out=. \
    messages/tg.proto
```