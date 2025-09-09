cmake_minimum_required(VERSION 3.16)
project(snow_angel_uav_app C)

# Use C11
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Export compile_commands.json for clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Public headers for BSP 
include_directories(${CMAKE_SOURCE_DIR}/include)

# Collect all BSP source files
file(GLOB BSP_SOURCES
    ${CMAKE_SOURCE_DIR}/src/bsp/*.c
)

# Create a static library
add_library(bsp STATIC ${BSP_SOURCES})

# Collect all app source files
file(GLOB APP_SOURCES
    ${CMAKE_SOURCE_DIR}/src/app/*.c
)

# Create executable
add_executable(${PROJECT_NAME} ${APP_SOURCES})

# Link BSP library to app
target_link_libraries(${PROJECT_NAME} PRIVATE bsp)