# 🚁 ReliefRoute — Disaster Relief Routing & Logistics Optimization

> **Real-time disaster mapping, vehicle routing optimization, and emergency news aggregation platform**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web_App-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Folium](https://img.shields.io/badge/Folium-Maps-77B829?style=flat)](https://python-visualization.github.io/folium/)

---

## 📋 What This Does

ReliefRoute is a full-stack web application for **disaster relief logistics**. It integrates real-time disaster event data, vehicle routing optimization, and emergency news — designed to help relief agencies distribute medical supplies efficiently during natural disasters.

Built around a case study of **Cyclone Idai** (Mozambique, 2019) with real health site coordinates.

---

## ✨ Key Features

### 1. Vehicle Routing Optimization (VRPTW)
- Uses **OpenRouteService API** to solve the Vehicle Routing Problem with Time Windows
- Multi-vehicle fleet dispatching to health sites
- Capacity constraints and service time windows
- Generates delivery schedules with arrival/departure times per station
- Interactive route visualization on Folium maps with color-coded vehicle paths

### 2. Real-Time Disaster Map
- Fetches live disaster events from **NASA EONET API** (Earth Observatory Natural Event Tracker)
- Filterable by date range, category (Earthquake, Flood, Wildfire, etc.), and geographic bounding box
- MarkerCluster visualization with event details
- Exportable event data as CSV, JSON, or GeoJSON

### 3. Disaster News Aggregator
- **NewsAPI** integration for real-time disaster-related news
- Keyword-filtered articles (earthquake, flood, hurricane, wildfire, tornado)
- Smart filtering to exclude non-disaster content

### 4. Geocoding & Custom Locations
- **Geopy/Nominatim** integration for address-to-coordinate conversion
- Custom depot and delivery point management
- CSV upload for batch health site data

---

## 📁 Project Structure

```
ReliefRoute/
├── app.py                           # Flask server (500 lines) — routing, maps, news
├── Routing_Optimization_Idai.ipynb  # Jupyter notebook — Cyclone Idai case study
├── idai_health_sites.csv            # Health facility coordinates (Mozambique)
├── templates/
│   ├── index.html                   # Main routing dashboard
│   ├── disaster_map.html            # NASA EONET disaster map
│   └── news.html                    # News aggregation page
├── static/
│   ├── script.js                    # Frontend logic
│   ├── style.css                    # Styling
│   └── images/                      # UI assets
└── README.md
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Flask, Python |
| Routing Engine | OpenRouteService (VRPTW solver) |
| Maps | Folium, MarkerCluster |
| Disaster Data | NASA EONET API |
| News | NewsAPI |
| Geocoding | Geopy / Nominatim |
| Geospatial | GeoPandas |
| Analysis | Pandas, Jupyter |

## 🚀 Quick Start

```bash
pip install flask folium openrouteservice newsapi-python geopy geopandas pandas
python app.py
# Open http://localhost:5000
```

## 👤 Author

**Piyush Ranjan Singh** — [GitHub](https://github.com/piewsh) • [Email](mailto:rajputpiyush2009@gmail.com)
