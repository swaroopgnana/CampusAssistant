import { useEffect, useState } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import "leaflet/dist/leaflet.css";
import { api, messageFromError } from "../api/client";

const pin = new L.Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

export default function Navigation() {
  const [locations, setLocations] = useState([]);
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [accessibleOnly, setAccessibleOnly] = useState(false);
  const [route, setRoute] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.get("/campus/locations").then(({ data }) => setLocations(data))
      .catch((requestError) => setError(messageFromError(requestError)));
  }, []);
  const findRoute = async (event) => {
    event.preventDefault();
    setError("");
    setRoute(null);
    setBusy(true);
    try {
      const { data } = await api.post("/navigation/route", null, {
        params: { origin_id: origin, destination_id: destination, accessible_only: accessibleOnly },
      });
      setRoute(data);
    } catch (requestError) {
      setError(messageFromError(requestError));
    } finally {
      setBusy(false);
    }
  };
  const coordinates = route?.locations
    .filter((location) => location.latitude != null && location.longitude != null)
    .map((location) => [location.latitude, location.longitude]);
  const center = coordinates?.[0] ?? locations.find((location) =>
    location.latitude != null && location.longitude != null);
  return <div className="page">
    <header className="page-header"><div><p className="eyebrow">GETTING AROUND</p><h1>Campus map</h1>
      <p className="muted">Routes use pathways entered by campus administrators.</p></div></header>
    <form className="card route-form" onSubmit={findRoute}>
      <label>Starting point<select required value={origin} onChange={(event) => setOrigin(event.target.value)}>
        <option value="">Choose a mapped location</option>
        {locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}
      </select></label>
      <label>Destination<select required value={destination} onChange={(event) => setDestination(event.target.value)}>
        <option value="">Choose a mapped location</option>
        {locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}
      </select></label>
      <label className="checkbox-label route-accessibility"><input type="checkbox" checked={accessibleOnly}
        onChange={(event) => setAccessibleOnly(event.target.checked)} /> Accessible pathways only</label>
      <button className="button button-primary" disabled={busy || !locations.length}>{busy ? "Finding route…" : "Find walking route"}</button>
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {!locations.length && !error && <p className="empty-state">Campus locations have not been added yet. Ask an administrator to configure the verified campus map.</p>}
    {route && <div className="route-summary">
      <strong>{route.distance_meters} m</strong><span> · about {route.estimated_walking_minutes} min walking</span>
      <p>{route.locations.map((location) => location.name).join(" → ")}</p>
    </div>}
    {center?.latitude != null && center?.longitude != null && <div className="map-frame">
      <MapContainer center={[center.latitude, center.longitude]} zoom={16} scrollWheelZoom className="campus-map">
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {(route?.locations ?? locations).filter((location) => location.latitude != null && location.longitude != null).map((location) =>
          <Marker key={location.id} position={[location.latitude, location.longitude]} icon={pin}>
            <Popup>{location.name}</Popup>
          </Marker>)}
        {coordinates?.length > 1 && <Polyline positions={coordinates} pathOptions={{ color: "#176c67", weight: 5 }} />}
      </MapContainer>
    </div>}
    {route && coordinates?.length !== route.locations.length && <p className="footnote">Some route points do not have coordinates yet, so the map can only show mapped points.</p>}
  </div>;
}
