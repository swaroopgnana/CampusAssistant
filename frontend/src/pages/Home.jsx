import { Link } from "react-router-dom";
import { useAuth } from "../state/AuthContext";

const shortcuts = [
  { to: "/chat", icon: "✦", title: "Ask Campus Pilot", desc: "Get help using verified campus information." },
  { to: "/events", icon: "◷", title: "Events & news", desc: "Discover published campus updates." },
  { to: "/timetable", icon: "▦", title: "My timetable", desc: "View your schedule by academic profile." },
  { to: "/lost-found", icon: "⌕", title: "Lost & Found", desc: "Submit or track an item report." },
];

export default function Home() {
  const { user } = useAuth();
  return (
    <div className="page">
      <header className="page-header">
        <div><p className="eyebrow">CAMPUS PILOT</p><h1>Good to see you, {user?.full_name?.split(" ")[0] ?? "there"}.</h1>
          <p className="muted">Your campus services, all in one place.</p></div>
      </header>
      <section className="hero">
        <div><p className="eyebrow light">YOUR CAMPUS ASSISTANT</p><h2>What do you need today?</h2>
          <p>Ask about campus services, find an event, or get started with a report.</p>
          <Link className="button button-light" to="/chat">Start a conversation <span aria-hidden="true">→</span></Link>
        </div>
        <div className="hero-mark" aria-hidden="true">✦</div>
      </section>
      <section className="section">
        <div className="section-heading"><h2>Quick access</h2><span className="muted">Pick up where you need to be</span></div>
        <div className="shortcut-grid">{shortcuts.map((item) =>
          <Link className="card shortcut" key={item.to} to={item.to}>
            <span className="shortcut-icon">{item.icon}</span><h3>{item.title}</h3><p>{item.desc}</p><span className="shortcut-arrow">↗</span>
          </Link>)}</div>
      </section>
      <p className="footnote">Campus information is shown only when it has been added by an authorized source.</p>
    </div>
  );
}
