# The crowd plane: a native process, C++, outside the BEAM.
#
# A plane has no networking. This one simulates and encodes fabric entity packets; an edge is
# a separate process that terminates a transport and hands frames over iceoryx2. See
# CLAUDE.md in weft.
#
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DMUJOCO_ROOT=/path/to/mujoco
#   cmake --build build -j
cmake_minimum_required(VERSION 3.22)
project(weft-crowd-plane LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(MUJOCO_ROOT "" CACHE PATH "MuJoCo with include/mujoco and libmujoco.so")
if(NOT MUJOCO_ROOT)
  message(FATAL_ERROR "set -DMUJOCO_ROOT to a MuJoCo install")
endif()
# A MuJoCo release puts the library in lib/ and the Python wheel puts it beside the headers.
# Accept both rather than making the caller know which one they have.
file(GLOB MUJOCO_LIB "${MUJOCO_ROOT}/lib/libmujoco.so*" "${MUJOCO_ROOT}/libmujoco.so*")
if(NOT MUJOCO_LIB)
  message(FATAL_ERROR "no libmujoco.so under ${MUJOCO_ROOT} or ${MUJOCO_ROOT}/lib")
endif()
list(GET MUJOCO_LIB 0 MUJOCO_LIB)
message(STATUS "MuJoCo: ${MUJOCO_LIB}")

add_executable(weft-crowd-plane src/plane.cpp)
target_include_directories(weft-crowd-plane PRIVATE include "${MUJOCO_ROOT}/include")
target_link_libraries(weft-crowd-plane PRIVATE "${MUJOCO_LIB}")
target_compile_options(weft-crowd-plane PRIVATE -O3)

enable_testing()
add_executable(tick_test test/tick_test.cpp)
target_include_directories(tick_test PRIVATE include)
add_test(NAME tick COMMAND tick_test)
