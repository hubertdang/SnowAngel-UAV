# Snow-Angel UAV

## UAV-Assisted Aerial Ice-Thickness Profiling

<img src=common/images/SnowAngelUAV.jpg height="650" width="450" >
<img src=common/images/Sebastian_Stan_as_Bucky_Barnes.jpg height="650" width="450" >

### Members

- Karran Dhillon (Team Lead)
- Hubert Dang
- Abdullah Baseem
- Suren Kulasegaram

## Project Description

Ice thickness profiling is crucial for skating, particularly on frozen lakes and rivers. For safe individual skating on ice, the city of Ottawa recommends a minimum thickness of 15 cm
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

### Web Visualization Prototype
```
SnowAngel-UAV/
    webapp/
        backend/        <- FastAPI service + Postgres seeding script
        frontend/       <- React landing page (Vite + React Leaflet)
```

The prototype adds:
- `/api/conditions` endpoint that streams geo-tagged heatmap points from Postgres.
- `scripts/seed_dummy_data.py` to populate Rideau Canal sample readings.
- React landing page with an upload modal, legend, and interactive heatmap that fetches new data whenever the map is panned.
 - React landing page with an upload modal and interactive heatmap that fetches new data whenever the map is panned, plus a date selector to jump between seeded condition days.


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

---
## Web Prototype
1. Ensure Docker (v20+) and Docker Compose are installed locally.
2. From the repo root run `./start.sh`. The script builds the frontend, backend, and Postgres images, then boots the stack via `docker compose up --build`.
3. Once the seed job finishes you can visit:
   - Frontend: http://localhost:4173
   - Backend docs: http://localhost:8000/docs
   - Postgres: localhost:5432 (user/pass/db: `snowangel`).
4. To re-seed dummy data at any time run `docker compose run --rm seed-data --count 220 --days 4` (matches `docker-compose.yml`) or execute `python webapp/backend/scripts/seed_dummy_data.py --count 220 --days 4` with the appropriate DB environment variables set. Re-run this whenever the synthetic data script changes to refresh the multi-day samples.

During local development you can also run each piece independently:
- Backend: `uvicorn server:app --reload --port 8000` inside `webapp/backend` (ensure a Postgres instance is running).
- Frontend: `npm install && npm run dev -- --host 0.0.0.0 --port 5173` inside `webapp/frontend` with `VITE_API_URL=http://localhost:8000`.
