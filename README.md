# Vaeris: AI-Powered Urban Air Quality Intelligence Platform

Vaeris is an intelligent intervention planning platform built for smart city administrators to manage air quality crises under strict operational constraints. 

Unlike traditional dashboards that only report current AQI, Vaeris predicts future pollution trajectories, attributes spikes to specific physical causes (using wind vector and NASA FIRMS data), and recommends resource-optimized inspector dispatch schedules using a formal mathematical objective.

---

## Repository Structure

```
vaeris/
├── .github/workflows/   # CI/CD Workflows (Black, Ruff, Pytest, Frontend build)
├── backend/
│   ├── config/          # Central settings, configuration, and optimization weights
│   ├── logging/         # Structured logger (Colored stdout & JSON file outputs)
│   ├── ingestion/       # API clients, normalization, and graceful degradation code
│   ├── models/          # LightGBM forecasting models, registry, and attribution logic
│   ├── decision/        # Multi-objective knapsack optimizer
│   ├── db/              # SQL migrations and database connection controllers
│   ├── api/             # FastAPI REST endpoints (/api/v1/...)
│   └── tests/           # Backend pytest suites
├── frontend/
│   ├── src/             # React dashboard components, maps (MapLibre GL), and layouts
│   └── vite.config.js   # Vite server settings & proxy definitions
├── data/
│   ├── raw/             # Raw historical datasets (gitignored)
│   ├── processed/       # Processed features and tables (gitignored)
│   └── snapshots/       # JSON offline snapshots (e.g., Delhi Nov 18, 2024 episode)
├── docs/
│   ├── architecture.md  # System Architecture & diagrams
│   └── README.md        # Documentation overview
├── docker-compose.yml   # Services config (PostgreSQL + PostGIS & Redis)
└── .gitignore           # Global git ignore configurations
```

---

## Core Tech Stack

*   **Database:** PostgreSQL + PostGIS (Spatial queries, wind intersections, road density joins)
*   **Caching:** Redis (15-min cache for forecasting, 30-min for attribution & decisions)
*   **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, PyYAML
*   **Machine Learning:** LightGBM (Quantile loss for uncertainty forecasting), SHAP (Inference explainability)
*   **Frontend:** React, MapLibre GL (Open-source geospatial map tiles), Recharts (Explainability waterfall charts)

---

## Setup & Local Run Instructions

### Prerequisites
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/)
*   [Python 3.10+](https://www.python.org/downloads/)
*   [Node.js 18+](https://nodejs.org/)

### 1. Run Services (Postgres/PostGIS & Redis)
From the root directory, spin up the local services container stack:
```bash
docker-compose up -d
```
Verify the healthcheck statuses of the containers using:
```bash
docker ps
```

### 2. Backend Setup
1. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Initialize environment file:
   ```bash
   cp .env.example .env
   ```
4. Start the backend developer server:
   ```bash
   uvicorn backend.api.main:app --reload --port 8000
   ```

### 3. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Spin up the Vite developer server:
   ```bash
   npm run dev
   ```
4. Open your browser and navigate to `http://localhost:3000`.

---

## Implementation Roadmap
Development follows a modular phase plan. Refer to the [Implementation Plan (v2)](implementation-plan-v2.md) for full phase-by-phase checkpoints and descriptions.
