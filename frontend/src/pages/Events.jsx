import { useEffect, useState } from "react";
import { api, messageFromError } from "../api/client";

function formatEventTime(value, timeZone) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(value));
}

export default function Events() {
  const [events, setEvents] = useState([]);
  const [news, setNews] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api.get("/events"), api.get("/news")])
      .then(([eventResponse, newsResponse]) => { setEvents(eventResponse.data); setNews(newsResponse.data); })
      .catch((requestError) => setError(messageFromError(requestError)));
  }, []);
  return <div className="page">
    <header className="page-header"><div><p className="eyebrow">WHAT'S ON CAMPUS</p><h1>Events & news</h1>
      <p className="muted">Official updates published by your college.</p></div></header>
    {error && <p className="error" role="alert">{error}</p>}
    <section className="section"><div className="section-heading"><h2>Upcoming events</h2><span className="muted">{events.length} published</span></div>
      {events.length ? <div className="content-grid">{events.map((event) => <article className="card content-card" key={event.id}>
        <p className="eyebrow">{formatEventTime(event.starts_at, event.timezone)}</p><h3>{event.title}</h3>
        <p>{event.description}</p>
        {event.location && <p className="muted">Location: {event.location}</p>}
        {event.organizer && <p className="muted">Hosted by {event.organizer}</p>}
        {event.registration_required && <p className="muted">Registration required</p>}
        {event.registration_url && <a href={event.registration_url} target="_blank" rel="noreferrer">Registration details ↗</a>}
      </article>)}</div> : <p className="empty-state">No published events to show right now.</p>}
    </section>
    <section className="section"><div className="section-heading"><h2>Campus news</h2><span className="muted">{news.length} published</span></div>
      {news.length ? <div className="content-grid">{news.map((item) => <article className="card content-card" key={item.id}>
        <p className="eyebrow">{item.category} · {new Date(item.published_at).toLocaleDateString()}</p>
        <h3>{item.title}</h3><p>{item.description}</p><p className="muted">Source: {item.source}</p>
      </article>)}</div> : <p className="empty-state">No published news to show right now.</p>}
    </section>
  </div>;
}
