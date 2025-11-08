cmake_minimum_required(VERSION 3.16)
project(snow_angel_uav_app C CXX)

# Use C11
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Use C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Export compile_commands.json for clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Collect all BSP source files
file(GLOB BSP_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/bsp/*.c
    ${CMAKE_CURRENT_SOURCE_DIR}/src/bsp/*.cpp
)

# Create a static library for BSP
add_library(bsp STATIC ${BSP_SOURCES})

# Tell CMake that anything linking bsp gets the include folder
target_include_directories(bsp PUBLIC ${CMAKE_SOURCE_DIR}/include)

# Collect all common source files
file(GLOB COMMON_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/common/*.c
)

# Create a static library for common
add_library(common STATIC ${COMMON_SOURCES})

# Tell CMake that anything linking common gets the include folder
target_include_directories(common PUBLIC ${CMAKE_SOURCE_DIR}/include)

# Collect all app source files
file(GLOB APP_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/app/*.c
    ${CMAKE_CURRENT_SOURCE_DIR}/src/app/*.cpp
)

# Add configurable build flags here
option(RADAR_SIMULATION "Enable RADAR simulation features" OFF)
option(BUILD_UNIT_TESTS "Build unit tests" OFF)

# if RADAR_SIMULATION is enabled, add the preprocessor directive
if(RADAR_SIMULATION)
    add_compile_definitions(RADAR_SIMULATION)
endif()

# If requested, add a simple unit test executable. Tests can be plain programs
# that implement a main() and use assert()/custom checks.
if(BUILD_UNIT_TESTS)
    enable_testing()

    # Collect all unit test sources under board/unittest
    file(GLOB UNIT_TEST_SOURCES
        ${CMAKE_CURRENT_SOURCE_DIR}/unittest/*.cpp
    )

    if(UNIT_TEST_SOURCES)
        # Create one executable per test source file. This lets each test have
        # its own main()
        foreach(test_src IN LISTS UNIT_TEST_SOURCES)
            get_filename_component(test_name ${test_src} NAME_WE)
            add_executable(${test_name} ${test_src})
            target_link_libraries(${test_name} PRIVATE bsp common)
            target_include_directories(${test_name} PRIVATE ${CMAKE_SOURCE_DIR}/include)
            add_test(NAME ${test_name} COMMAND ${test_name})
        endforeach()
    else()
        message(WARNING "BUILD_UNIT_TESTS is ON but no test sources found in ${CMAKE_CURRENT_SOURCE_DIR}/unittest")
    endif()
endif()

# Create executable for the app
add_executable(${PROJECT_NAME} ${APP_SOURCES})

# Link static libraries to app
target_link_libraries(${PROJECT_NAME} PRIVATE bsp)
target_link_libraries(${PROJECT_NAME} PRIVATE common)
