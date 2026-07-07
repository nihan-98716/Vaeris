# Vaeris Historical Replay Snapshots

This directory contains pre-processed, aligned offline data snapshots used to power the **Historical Replay** feature of the dashboard.

## Delhi Event (November 13–18, 2024)

*   **File:** `delhi_2024-11-13_to_2024-11-18.json`
*   **Target Episode:** Severe stubble-burning event in Delhi NCR. On **November 18, 2024**, Delhi's 24h average AQI peaked at **491 (Severe Plus)**, with PM2.5 levels climbing past 600 µg/m³. GRAP-III protocols were activated on November 14.
*   **Included Stations:**
    1.  **Anand Vihar (DL001):** Traffic-dominant hot spot in East Delhi.
    2.  **Narela (DL002):** Industrial-dominant hot spot in North Delhi.
    3.  **Bawana (DL003):** Northwest border station (closest to smoke transport boundary).
    4.  **RK Puram (DL004):** Residential/commercial composite in South Delhi.
    5.  **Mandir Marg (DL005):** Background benchmark station in Central Delhi.
*   **Contents:**
    *   **metadata:** Details about target city, coordinates, types, and geometries of the 5 representative stations.
    *   **aqi_data:** 720 records of hourly AQI, PM2.5, and PM10 values.
    *   **fire_data:** 700 active fire hotspots coordinates, acquisition times, brightness, and FRP (Fire Radiative Power) outputs.
    *   **weather_data:** 144 records of hourly temperature, relative humidity, wind speed, and wind direction (capturing the NW wind shifts on Nov 17-18).
    *   **osm_data:** Cached OSM highway road counts in proximity of stations to proxy traffic density.
