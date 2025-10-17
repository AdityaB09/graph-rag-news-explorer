cmake_minimum_required(VERSION 3.16)
project(graph_engine CXX)
set(CMAKE_CXX_STANDARD 17)

find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

set(PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/proto)
set(PROTO ${PROTO_DIR}/graph_engine.proto)
set(GEN_DIR ${CMAKE_CURRENT_BINARY_DIR}/generated)
file(MAKE_DIRECTORY ${GEN_DIR})

get_target_property(Protobuf_PROTOC_EXECUTABLE protobuf::protoc LOCATION)
if(NOT Protobuf_PROTOC_EXECUTABLE)
  find_program(Protobuf_PROTOC_EXECUTABLE protoc)
endif()
find_program(GRPC_CPP_PLUGIN_EXECUTABLE grpc_cpp_plugin)

if(NOT Protobuf_PROTOC_EXECUTABLE)
  message(FATAL_ERROR "protoc not found")
endif()
if(NOT GRPC_CPP_PLUGIN_EXECUTABLE)
  message(FATAL_ERROR "grpc_cpp_plugin not found")
endif()

set(PROTO_SRCS
  ${GEN_DIR}/graph_engine.pb.cc
  ${GEN_DIR}/graph_engine.grpc.pb.cc
)
set(PROTO_HDRS
  ${GEN_DIR}/graph_engine.pb.h
  ${GEN_DIR}/graph_engine.grpc.pb.h
)

add_custom_command(
  OUTPUT ${GEN_DIR}/graph_engine.pb.cc ${GEN_DIR}/graph_engine.pb.h
  COMMAND ${Protobuf_PROTOC_EXECUTABLE}
          -I ${PROTO_DIR}
          --cpp_out=${GEN_DIR}
          ${PROTO}
  DEPENDS ${PROTO}
  COMMENT "Generating protobuf C++ files"
)
add_custom_command(
  OUTPUT ${GEN_DIR}/graph_engine.grpc.pb.cc ${GEN_DIR}/graph_engine.grpc.pb.h
  COMMAND ${Protobuf_PROTOC_EXECUTABLE}
          -I ${PROTO_DIR}
          --grpc_out=${GEN_DIR}
          --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN_EXECUTABLE}
          ${PROTO}
  DEPENDS ${PROTO}
  COMMENT "Generating gRPC C++ files"
)

add_library(graph_proto ${PROTO_SRCS} ${PROTO_HDRS})
target_include_directories(graph_proto PUBLIC ${GEN_DIR})
target_link_libraries(graph_proto PUBLIC protobuf::libprotobuf gRPC::grpc++)

add_library(engine_objs src/engine.cpp)
target_include_directories(engine_objs PUBLIC src)

add_executable(graph_engine_server src/server.cpp)
target_include_directories(graph_engine_server PRIVATE ${GEN_DIR})
target_link_libraries(graph_engine_server PRIVATE engine_objs graph_proto gRPC::grpc++ protobuf::libprotobuf)
