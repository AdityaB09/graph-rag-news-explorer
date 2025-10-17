cmake_minimum_required(VERSION 3.16)
project(htmlfast LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# --- pybind11 (prefer system; fallback to FetchContent) ---
find_package(pybind11 QUIET)
if(NOT pybind11_FOUND)
  include(FetchContent)
  FetchContent_Declare(
    pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG v2.13.1
  )
  FetchContent_MakeAvailable(pybind11)
endif()

# --- Gumbo via pkg-config ---
find_package(PkgConfig REQUIRED)
pkg_check_modules(GUMBO REQUIRED gumbo)

# Build the Python extension module
pybind11_add_module(htmlfast
  src/bindings.cpp
  src/html_parser.cpp
)

target_include_directories(htmlfast PRIVATE
  ${GUMBO_INCLUDE_DIRS}
  ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_compile_options(htmlfast PRIVATE
  ${GUMBO_CFLAGS_OTHER}
)

target_link_libraries(htmlfast PRIVATE
  ${GUMBO_LIBRARIES}
)
