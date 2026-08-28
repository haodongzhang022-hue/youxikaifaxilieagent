cmake_minimum_required(VERSION 3.16)
project(game_middleware CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -fvisibility=hidden")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fvisibility=hidden")

include_directories(include)

# 核心静态库
add_library(game_middleware STATIC
    src/common/CabiCommon.cpp
    src/gameplay/GameplayCore.cpp
    src/combat/CombatCore.cpp
    src/procgen/ProcgenCore.cpp
    src/numeric/FixedPoint.cpp
)

# C ABI 动态库（对外导出）
add_library(game_middleware_abi SHARED
    src/cabi/cabi_common.cpp
    src/cabi/cabi_gameplay.cpp
    src/cabi/cabi_combat.cpp
    src/cabi/cabi_procgen.cpp
    src/cabi/cabi_numeric.cpp
)
target_link_libraries(game_middleware_abi PRIVATE game_middleware)

# 测试可执行
enable_testing()
add_executable(test_core tests/test_core.cpp)
target_link_libraries(test_core PRIVATE game_middleware_abi)
add_test(NAME core_test COMMAND test_core)
