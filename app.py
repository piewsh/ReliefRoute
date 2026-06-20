# -*- coding: utf-8 -*-
import os
import json
import tempfile, glob
from io import BytesIO
import zipfile
from io import StringIO
from flask import send_file
from flask import jsonify, Response, send_file, flash, redirect, url_for
import geopandas as gpd
from datetime import datetime
from flask import session
from flask import Flask, render_template, request, redirect, flash, url_for, make_response
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import requests
import openrouteservice as ors
from openrouteservice import convert
from newsapi import NewsApiClient
from geopy.geocoders import Nominatim

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key")

# API Keys
ORS_API_KEY = os.getenv("ORS_API_KEY", "")  # Your ORS key
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "0ad077e6f6784b98989edd1936bdb066")  # Your NewsAPI key

geolocator = Nominatim(user_agent="reliefroute")

# Initialize NewsAPI client
newsapi = NewsApiClient(api_key=NEWSAPI_KEY)

# ----------------------------------------
# NewsAPI Helper
# ----------------------------------------
def fetch_disaster_news():
    """Fetch the latest disaster-related news articles using NewsAPI."""
    q = (
        '("earthquake" AND ("disaster" OR "emergency" OR "warning")) OR '
        '("flood" AND ("disaster" OR "emergency" OR "warning")) OR '
        '("hurricane" AND ("disaster" OR "emergency" OR "warning")) OR '
        '("wildfire" AND ("disaster" OR "emergency" OR "warning")) OR '
        '("tornado" AND ("disaster" OR "emergency" OR "warning"))'
    )
    
    resp = newsapi.get_everything(
        q=q,
        language="en",
        sort_by="publishedAt",
        page_size=10,
    )
    
    if resp.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {resp.get('code')} - {resp.get('message')}")
    
    articles = resp.get("articles", [])
    out = []
    
    for a in articles:
        if is_disaster_related(a):
            out.append({
                "source": a["source"]["name"],
                "title": a["title"],
                "author": a.get("author") or "Unknown",
                "published_at": pd.to_datetime(a["publishedAt"]).strftime("%Y-%m-%d %H:%M:%S"),
                "url": a["url"],
            })
    
    return out

def is_disaster_related(article):
    """Check if the article is likely disaster-related based on its title."""
    exclude_keywords = ["project", "climate change", "sports", "entertainment", "food", "economy"]
    title = article["title"].lower()
    for keyword in exclude_keywords:
        if keyword in title:
            return False
    return True

# ----------------------------------------
# ORS / Folium Helpers
# ----------------------------------------
def plain_map():
    """Generate a plain Folium map for the initial GET request."""
    m = folium.Map(location=[-19.818474, 34.835447], zoom_start=3, tiles="cartodbpositron")
    return m._repr_html_()

def create_map(df=None, depot=None, result=None):
    """Generate a Folium map with delivery points, depot, and routes if provided."""
    if depot:
        m = folium.Map(location=depot, zoom_start=3, tiles="cartodbpositron")
        folium.Marker(depot, icon=folium.Icon(color="green", icon="home"), tooltip="Depot").add_to(m)
    else:
        m = folium.Map(location=[-19.818474, 34.835447], zoom_start=3, tiles="cartodbpositron")

    if df is not None and not df.empty:
        for idx, row in df.iterrows():
            folium.CircleMarker(
                location=[row.Lat, row.Lon],
                radius=7,
                color="#ff6f61",
                fill=True,
                fill_color="#ff9f80",
                fill_opacity=0.8,
                tooltip=f"ID {idx}: {row.Needed_Amount}"
            ).add_to(m)

    if result and "routes" in result:
        colors = ["green", "red", "blue", "purple", "orange"]
        for color, route in zip(colors, result["routes"]):
            decoded = convert.decode_polyline(route["geometry"])
            gj = folium.GeoJson(
                decoded,
                style_function=lambda feat, col=color: {"color": col, "weight": 4},
            )
            gj.add_child(folium.Tooltip(
                f"<b>Vehicle {route['vehicle']}</b><br>"
                f"Distance: {route['distance']} m<br>"
                f"Duration: {route['duration']} s"
            ))
            gj.add_to(m)
        folium.LayerControl().add_to(m)

    return m._repr_html_()

def generate_schedules(result):
    """Generate schedules and summary tables from optimization results."""
    schedules, summary = [], []
    for route in result.get("routes", []):
        steps = []
        for step in route.get("steps", []):
            job = step.get("job", "Depot")
            arr = pd.to_datetime(step["arrival"], unit="s")
            dep = arr + pd.to_timedelta(step.get("service", 0), unit="s")
            steps.append([job, arr, dep])
        df_sched = pd.DataFrame(steps, columns=["Station ID", "Arrival", "Departure"])
        schedules.append(
            (f"Vehicle {route['vehicle']}", df_sched.to_html(classes="table table-striped", index=False))
        )
        summary.append({
            "Vehicle": route["vehicle"],
            "Distance_m": route["distance"],
            "Duration_s": route["duration"],
            "Amount": route.get("amount", "")
        })
    df_sum = pd.DataFrame(summary).set_index("Vehicle")
    return schedules, df_sum.to_html(classes="table table-striped")

def create_disaster_map(start_date, end_date, category, bbox=None):
    """Fetch EONET events and return (map_html, events_list) with keys Title, Date, Latitude, Longitude, Category."""
    url = "https://eonet.gsfc.nasa.gov/api/v3/events"
    params = {"start": start_date, "end": end_date, "status": "open"}
    if category != "All":
        params["category"] = category

    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        raw_events = resp.json().get("events", [])
    except Exception as e:
        flash(f"Failed to fetch EONET events: {e}", "danger")
        raw_events = []

    # Build the folium map
    m = folium.Map(location=[0, 0], zoom_start=2, tiles="cartodbpositron")
    cluster = MarkerCluster().add_to(m)
    events_list = []

    for ev in raw_events:
        title = ev.get("title")
        cat_title = ev.get("categories", [{}])[0].get("title", "")
        for geom in ev.get("geometry", []):
            date = geom.get("date")
            lon, lat = geom.get("coordinates", [None, None])
            if lat is None or lon is None:
                continue

            if bbox:
                south, north, west, east = bbox
                if not (south <= lat <= north and west <= lon <= east):
                    continue

            folium.Marker(
                location=[lat, lon],
                popup=(
                    f"<b>{title}</b><br>"
                    f"Category: {cat_title}<br>"
                    f"Date: {date}<br>"
                    f"<a href='{ev.get('link','#')}' target='_blank'>More Info</a>"
                ),
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(cluster)

            events_list.append({
                "Title": title,
                "Date": date,
                "Latitude": lat,
                "Longitude": lon,
                "Category": cat_title
            })

    return m._repr_html_(), events_list

# ----------------------------------------
# Routes
# ----------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    """Handle GET (initial page) and POST (form submission) requests."""
    images = sorted(
        f for f in os.listdir(os.path.join(app.static_folder, "images"))
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
    )

    if request.method == "POST":
        api_key = request.form.get("ors_key", ORS_API_KEY).strip()
        depot_lat = request.form.get("depot_lat")
        depot_lon = request.form.get("depot_lon")
        num_vehicles = request.form.get("num_vehicles")
        capacity = request.form.get("capacity")
        service_time = request.form.get("service_time")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        delivery_json = request.form.get("delivery_points")
        csv_file = request.files.get("csv_file")

        # Validate required fields
        for name, val in [
            ("Vehicles", num_vehicles),
            ("Capacity", capacity),
            ("Service Time", service_time),
            ("Start Time", start_time),
            ("End Time", end_time),
        ]:
            if not val:
                flash(f"{name} is required.", "danger")
                return redirect(url_for("index"))

        # Validate numeric inputs
        try:
            num_vehicles = int(num_vehicles)
            capacity = int(capacity)
            service_time = int(service_time)
            start_ts = int(float(start_time))
            end_ts = int(float(end_time))
            if num_vehicles <= 0 or capacity <= 0 or service_time <= 0:
                raise ValueError("Values must be positive")
            if start_ts >= end_ts:
                raise ValueError("Start must be before End")
        except Exception as e:
            flash(f"Invalid numeric input: {e}", "danger")
            return redirect(url_for("index"))

        # Validate depot coordinates
        try:
            depot = [float(depot_lat), float(depot_lon)]
            if not (-90 <= depot[0] <= 90 and -180 <= depot[1] <= 180):
                raise ValueError()
        except:
            flash("Invalid depot coordinates.", "danger")
            return redirect(url_for("index"))

        # Process delivery points (manual JSON or CSV)
        if csv_file and csv_file.filename:
            try:
                import csv
                sample = csv_file.stream.read(1024)
                dialect = csv.Sniffer().sniff(sample.decode('utf-8', errors='ignore'))
                csv_file.stream.seek(0)

                df = pd.read_csv(
                    csv_file,
                    index_col="ID",
                    sep=dialect.delimiter,
                )
                required = ["Lon", "Lat", "Needed_Amount", "Open_From", "Open_To"]
                if not all(c in df.columns for c in required):
                    raise ValueError(f"CSV must include {required}")
                for col in ["Open_From", "Open_To"]:
                    nums = pd.to_numeric(df[col], errors="coerce")
                    dt = pd.Series(index=df.index, dtype="datetime64[ns]")
                    mask = nums.notna()
                    dt[mask] = pd.to_datetime(nums[mask].astype(int), unit="s")
                    dt[~mask] = pd.to_datetime(df.loc[~mask, col], dayfirst=True, format="mixed")
                    df[col] = dt
                df[["Lon", "Lat"]] = df[["Lon", "Lat"]].astype(float)
                df["Needed_Amount"] = df["Needed_Amount"].astype(int)
            except Exception as e:
                flash(f"Failed to parse CSV: {e}", "danger")
                return redirect(url_for("index"))
        elif delivery_json and delivery_json.strip() != "[]":
            try:
                pts = json.loads(delivery_json)
                if not pts:
                    raise ValueError("Manual points are empty")
                df = pd.DataFrame(pts).set_index("ID")
                df[["Lon", "Lat"]] = df[["Lon", "Lat"]].astype(float)
                df["Needed_Amount"] = df["Needed_Amount"].astype(int)
                df["Open_From"] = pd.to_datetime(df["Open_From"].astype(int), unit="s")
                df["Open_To"] = pd.to_datetime(df["Open_To"].astype(int), unit="s")
            except Exception as e:
                flash(f"Failed to parse manual points: {e}", "danger")
                return redirect(url_for("index"))
        else:
            flash("Please upload a CSV or add points on the map.", "danger")
            return redirect(url_for("index"))

        # Check for out-of-bounds coordinates
        bad = df[(df.Lat.abs() > 90) | (df.Lon.abs() > 180)]
        if not bad.empty:
            flash(f"Point ID(s) {bad.index.tolist()} out of bounds.", "danger")
            return redirect(url_for("index"))

        # Perform route optimization
        try:
            client = ors.Client(key=api_key or ORS_API_KEY)
            vehicles = [
                ors.optimization.Vehicle(
                    id=i,
                    start=[depot[1], depot[0]],
                    capacity=[capacity],
                    time_window=[start_ts, end_ts]
                ) for i in range(num_vehicles)
            ]
            jobs = [
                ors.optimization.Job(
                    id=int(idx),
                    location=[row.Lon, row.Lat],
                    service=service_time,
                    amount=[row.Needed_Amount],
                    time_windows=[[int(row.Open_From.timestamp()), int(row.Open_To.timestamp())]]
                ) for idx, row in df.iterrows()
            ]
            result = client.optimization(jobs=jobs, vehicles=vehicles, geometry=True)
            map_html = create_map(df, depot, result)
            schedules, summary = generate_schedules(result)
        except Exception as e:
            flash(f"Optimization failed: {e}", "danger")
            map_html, schedules, summary = create_map(df, depot), [], None

        news = []

        resp = make_response(render_template(
            "index.html",
            images=images,
            map_html=map_html,
            result=True,
            overall_table=df.to_html(classes="table table-striped"),
            schedules=schedules,
            vehicle_summary=summary,
            news=news,
        ))
    else:
        resp = make_response(render_template(
            "index.html",
            images=images,
            map_html=plain_map(),
            result=False,
            overall_table=None,
            schedules=[],
            vehicle_summary=None,
            news=[],
        ))

    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route("/disaster", methods=["GET", "POST"])
def disaster_map():
    """Render the disaster map page with EONET events."""
    cats = ["All"] + sorted([
        "drought", "dustHaze", "earthquakes", "floods", "landslides", "manmade",
        "seaLakeIce", "severeStorms", "snow", "tempExtremes", "volcanoes", "waterColor", "wildfires"
    ])
    selected_place = None
    bbox = None

    if request.method == "POST":
        sd = request.form.get("start_date")
        ed = request.form.get("end_date")
        cat = request.form.get("category", "All")
        selected_place = request.form.get("place", "").strip()

        if selected_place:
            try:
                loc = geolocator.geocode(selected_place, exactly_one=True, timeout=10)
                if loc and loc.raw.get("boundingbox"):
                    south, north, west, east = map(float, loc.raw["boundingbox"])
                    bbox = (south, north, west, east)
                else:
                    flash(f"Could not geocode '{selected_place}'. Using world view.", "warning")
                session['place'] = selected_place
            except Exception as e:
                flash(f"Geocoding error: {e}", "danger")

        session['disaster_params'] = {
            'start_date': sd,
            'end_date': ed,
            'category': cat,
            'place': selected_place
        }

        map_html, events = create_disaster_map(sd, ed, cat, bbox=bbox)

        return render_template(
            "disaster_map.html",
            categories=cats,
            map_html=map_html,
            events=events,
            selected_category=cat,
            start_date=sd,
            end_date=ed,
            selected_place=selected_place
        )

    return render_template(
        "disaster_map.html",
        categories=cats,
        map_html=None,
        events=[],
        selected_category="All",
        start_date=None,
        end_date=None,
        selected_place=None
    )

@app.route("/news_page")
def news_page():
    """Render the news page with the latest disaster news."""
    try:
        articles = fetch_disaster_news()
    except Exception as e:
        flash(f"Error fetching news: {e}", "danger")
        articles = []
    return render_template("news.html", articles=articles)

@app.route("/download_disaster_csv")
def download_disaster_csv():
    params = session.get('disaster_params')
    if not params:
        flash("No disaster parameters available. Please load events first.", "warning")
        return redirect(url_for('disaster_map'))

    url = "https://eonet.gsfc.nasa.gov/api/v3/events"
    api_params = {
        "start": params['start_date'],
        "end": params['end_date'],
        "status": "open"
    }
    if params['category'] != "All":
        api_params["category"] = params['category']

    try:
        resp = requests.get(url, params=api_params)
        resp.raise_for_status()
        raw_events = resp.json().get("events", [])
    except Exception as e:
        flash(f"Failed to fetch EONET events: {e}", "danger")
        return redirect(url_for('disaster_map'))

    events_list = []
    for ev in raw_events:
        title = ev.get("title", "")
        category_title = ev.get("categories", [{}])[0].get("title", "")
        for geom in ev.get("geometry", []):
            date = geom.get("date", "")
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    events_list.append({
                        "Title": title,
                        "Date": date,
                        "Latitude": lat,
                        "Longitude": lon,
                        "Category": category_title
                    })

    if not events_list:
        flash("No disaster events available to download.", "warning")
        return redirect(url_for('disaster_map'))

    df = pd.DataFrame(events_list)
    csv_io = StringIO()
    df.to_csv(csv_io, index=False)
    csv_bytes = csv_io.getvalue().encode('utf-8')

    return send_file(
        BytesIO(csv_bytes),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"disaster_events_{datetime.now().strftime('%Y%m%d')}.csv"
    )

if __name__ == "__main__":
    app.run(debug=True)