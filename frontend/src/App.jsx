import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Admin from "./pages/Admin";
import Chat from "./pages/Chat";
import Events from "./pages/Events";
import Home from "./pages/Home";
import Login from "./pages/Login";
import LostFound from "./pages/LostFound";
import Navigation from "./pages/Navigation";
import Timetable from "./pages/Timetable";

export default function App() {
  return <Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
      <Route index element={<Home />} />
      <Route path="chat" element={<Chat />} />
      <Route path="events" element={<Events />} />
      <Route path="timetable" element={<Timetable />} />
      <Route path="navigation" element={<Navigation />} />
      <Route path="lost-found" element={<LostFound />} />
      <Route path="admin" element={<ProtectedRoute adminOnly><Admin /></ProtectedRoute>} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}
