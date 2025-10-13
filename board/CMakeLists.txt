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

# Collect all app source files
file(GLOB APP_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/app/*.c
    ${CMAKE_CURRENT_SOURCE_DIR}/src/app/*.cpp
)

# Add configurable build flags
option(RADAR_SIMULATION "Enable RADAR simulation features" OFF)

# if RADAR_SIMULATION is enabled, add the preprocessor directive
if(RADAR_SIMULATION)
    add_compile_definitions(RADAR_SIMULATION)
endif()

# Create executable for the app
add_executable(${PROJECT_NAME} ${APP_SOURCES})

# Link static libraries to app
target_link_libraries(${PROJECT_NAME} PRIVATE bsp)
