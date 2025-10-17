# services/graph_engine/Dockerfile
FROM debian:12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git pkg-config \
    libprotobuf-dev protobuf-compiler protobuf-compiler-grpc \
    libgrpc++-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /engine
COPY . /engine
RUN cmake -S . -B build && cmake --build build --config Release

EXPOSE 50061
CMD ["./build/graph_engine_server"]
