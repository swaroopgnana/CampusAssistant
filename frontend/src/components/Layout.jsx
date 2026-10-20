import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../state/AuthContext";

export default function Layout() {
  const { user, token, signOut } = useAuth();
  const [notification, setNotification] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    if (!token || user?.role !== "admin") return undefined;
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${scheme}//${window.location.host}/api/v1/notifications/ws`);
    socket.onopen = () => socket.send(token);
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setNotification(payload.message);
        window.setTimeout(() => setNotification(""), 7000);
      } catch {
        setNotification("A new campus notification is available.");
      }
    };
    return () => socket.close();
  }, [token, user?.role]);
  const logout = () => {
    signOut();
    navigate("/login");
  };
  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/">Campus Pilot<span>YOUR CAMPUS, IN ONE PLACE</span></NavLink>
        <nav aria-label="Main navigation">
          <NavLink to="/">Overview</NavLink>
          <NavLink to="/chat">Ask Campus Pilot</NavLink>
          <NavLink to="/events">Events & news</NavLink>
          <NavLink to="/timetable">My timetable</NavLink>
          <NavLink to="/navigation">Campus map</NavLink>
          <NavLink to="/lost-found">Lost & Found</NavLink>
          {user?.role === "admin" && <NavLink to="/admin">Admin dashboard</NavLink>}
        </nav>
        <div className="sidebar-bottom">
          <span>{user?.full_name ?? "Campus visitor"}</span>
          <button className="button button-quiet" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main-content">
        {notification && <div className="notification" role="status">{notification}</div>}
        <Outlet />
      </main>
    </div>
  );
}
