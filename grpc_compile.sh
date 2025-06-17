rm -rf protos_compiled
mkdir protos_compiled
python -m grpc_tools.protoc -I./protos --python_out=./protos_compiled --grpc_python_out=./protos_compiled ./protos/*
echo "from . import *" >> protos_compiled/__init__.py