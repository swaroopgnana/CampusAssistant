import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../state/AuthContext";

export default function ProtectedRoute({ children, adminOnly = false }) {
  const { token, user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <main className="page"><p className="muted">Checking your session…</p></main>;
  if (!token) return <Navigate to="/login" state={{ from: location }} replace />;
  if (adminOnly && user?.role !== "admin") return <Navigate to="/" replace />;
  return children;
}
