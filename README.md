# Snow-Angel UAV

## UAV-Assisted Aerial Ice-Thickness Profiling

<img src=common/images/SnowAngelUAV.jpg>

### Members

- Karran Dhillon (Team Lead)
- Hubert Dang
- Abdullah Baseem
- Suren Kulasegaram

## Project Description

Ice thickness profiling is crucial for skating, particularly on frozen lakes and rivers. For safe individual skiing on ice, the city of Ottawa recommends a minimum thickness of 15 cm
(6 inches) of clear, solid ice. This guideline applies only in cases of hockey games or group skating. Currently, two methods are used to measure ice thickness: an auger and a hot-wire ice
thickness gauge. Both methods have some limitations in terms of applicability and accuracy. 

In this project, a novel UAV-assisted system is proposed and developed for profiling aerial ice thickness. This system is capable of performing the profiling without the need for physical
drilling. The goal is to collect localized data over areas like the Rideau Canal to help answer practical questions, such as whether it is safe to skate, which sections require additional
flooding, or if conditions are suitable for skating on local ponds. This approach offers a non-invasive and efficient alternative to traditional ice thickness measurements, focusing on enhancing
safety and informed decision-making in winter activities, such as skating on the canal.

## Software Organization
### Drone Subsystem 
```
SnowAngel-UAV/
    board/
        CMakeLists.txt
        include/
           bsp/  <- BSP public headers
        src/
            app/ <- Application code and private headers
            bsp/ <- BSP code and private headers
```


### Setup Instructions
---
## Drone Subsystem
1) Run Cmake to generate the Makefile

    1.1) Navigate to build folder (note you may need to mkdir it)
    >`hubert@hubertlaptop:~/SnowAngel-UAV$ cd board/build/`
    
    1.2) Run cmake
    >`hubert@hubertlaptop:~/SnowAngel-UAV/board/build$ cmake ..`

2) Build the project
    >`hubert@hubertlaptop:~/SnowAngel-UAV/board/build$ make`

3) Run the executable
    >`hubert@hubertlaptop:~/SnowAngel-UAV/board/build$ ./snow_angel_uav_app`

**Alternative** use the bash script automating the entire process
1) Run the script from the repo root directory
>`./mk`