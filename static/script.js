let map, depotMarker;
const deliveryMarkers = [];

function initMap() {
  // Remove any existing Folium map divs
  document.querySelectorAll('[id^=map_]').forEach(el => el.remove());

  // Remove existing map if it exists
  if (map) {
    map.remove();
  }

  // Initialize Leaflet map with center at [0, 0] and zoom level 1 to show the whole world
  map = L.map('map').setView([0, 0], 1);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  // Clear existing markers
  if (depotMarker) {
    map.removeLayer(depotMarker);
    depotMarker = null;
  }
  deliveryMarkers.forEach(pt => map.removeLayer(pt.marker));
  deliveryMarkers.length = 0;
  updateDeliveryList();
}

// Only run interactive map logic if result is false (initial GET state)
if (!window.isResult) {
  // Select Depot
  document.getElementById('select-depot').addEventListener('click', () => {
    // Remove any existing click listeners to prevent duplicates
    map.off('click');
    map.once('click', e => {
      const { lat, lng } = e.latlng;
      document.getElementById('depot_lat').value = lat.toFixed(6);
      document.getElementById('depot_lon').value = lng.toFixed(6);
      if (depotMarker) {
        map.removeLayer(depotMarker);
      }
      depotMarker = L.marker([lat, lng], {
        icon: L.icon({
          iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
          iconSize: [25, 41],
          iconAnchor: [12, 41],
        }),
      }).addTo(map).bindPopup('Depot').openPopup();
    });
  });

  // Add Delivery Point
  document.getElementById('add-delivery').addEventListener('click', () => {
    // Remove any existing click listeners to prevent duplicates
    map.off('click');
    map.once('click', addDeliveryPoint);
  });

  // Clear Delivery Markers
  document.getElementById('clear-delivery').addEventListener('click', () => {
    deliveryMarkers.forEach(pt => map.removeLayer(pt.marker));
    deliveryMarkers.length = 0;
    updateDeliveryList();
  });

  // Clear Entire Form & Reset (reload to GET)
  document.getElementById('clear-form').addEventListener('click', () => {
    window.location.href = '/';
  });

  function addDeliveryPoint(e) {
    const { lat, lng } = e.latlng;
    const id = deliveryMarkers.length + 1;
    const marker = L.marker([lat, lng]).addTo(map).bindPopup(`ID ${id}`).openPopup();
    deliveryMarkers.push({ id, lat, lng, marker, data: {} });
    updateDeliveryList();
  }

  function updateDeliveryList() {
    const list = document.getElementById('delivery-points');
    list.innerHTML = '';
    deliveryMarkers.forEach(pt => {
      const div = document.createElement('div');
      div.className = 'delivery-point mb-2 p-2 border rounded';
      div.innerHTML = `
        <h6>ID ${pt.id}</h6>
        <div class="row g-1 mb-1">
          <div class="col"><input class="form-control" value="${pt.lng.toFixed(6)}" disabled></div>
          <div class="col"><input class="form-control" value="${pt.lat.toFixed(6)}" disabled></div>
        </div>
        <input type="number" class="form-control mb-1" placeholder="Needed Amount" min="1"
          value="${pt.data.needed_amount || ''}"
          oninput="updatePt(${pt.id}, 'needed_amount', this.value)">
        <input type="number" class="form-control mb-1" placeholder="Open From (Unix)"
          value="${pt.data.open_from || ''}"
          oninput="updatePt(${pt.id}, 'open_from', this.value)">
        <input type="number" class="form-control mb-1" placeholder="Open To (Unix)"
          value="${pt.data.open_to || ''}"
          oninput="updatePt(${pt.id}, 'open_to', this.value)">
        <button class="btn btn-danger btn-sm" onclick="removePt(${pt.id})">Remove</button>
      `;
      list.appendChild(div);
    });
    updateHidden();
  }

  window.updatePt = (id, field, val) => {
    const pt = deliveryMarkers.find(d => d.id === id);
    if (pt) {
      pt.data[field] = val;
      updateHidden();
    }
  };

  window.removePt = id => {
    const idx = deliveryMarkers.findIndex(d => d.id === id);
    if (idx > -1) {
      map.removeLayer(deliveryMarkers[idx].marker);
      deliveryMarkers.splice(idx, 1);
      updateDeliveryList();
    }
  };

  function updateHidden() {
    const arr = deliveryMarkers.map(d => ({
      ID: d.id,
      Lon: d.lng,
      Lat: d.lat,
      Needed_Amount: parseInt(d.data.needed_amount) || 100,
      Open_From: parseInt(d.data.open_from) || 1553241600,
      Open_To: parseInt(d.data.open_to) || 1553284800,
    }));
    document.getElementById('delivery_points').value = JSON.stringify(arr);
  }
}

// Initialize map on page load
window.addEventListener('load', () => {
  if (!window.isResult) {
    initMap();
  }
});