FROM python:3.11-slim

# Build deps for pybind11 + gumbo + gRPC tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git curl pkg-config \
    libgumbo-dev \
    libprotobuf-dev protobuf-compiler protobuf-compiler-grpc \
    libgrpc++-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Build htmlfast (pybind11 + Gumbo)
COPY app/htmlfast /app/htmlfast
WORKDIR /app/htmlfast
RUN chmod +x ./build.sh && ./build.sh

# Return to /app; ensure Python can import
WORKDIR /app
ENV PYTHONPATH="/app:/app/app:/app/htmlfast:${PYTHONPATH}"


# API code
COPY app /app/app

# Generate Python gRPC stubs (client)
RUN python -m grpc_tools.protoc \
    -I/app/app/proto \
    --python_out=/app/app \
    --grpc_python_out=/app/app \
    /app/app/proto/graph_engine.proto

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
