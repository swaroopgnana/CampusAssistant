import { useEffect, useState } from "react";
import { api, messageFromError } from "../api/client";
import { useAuth } from "../state/AuthContext";

const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function Timetable() {
  const { user, setUser } = useAuth();
  const [entries, setEntries] = useState([]);
  const [nextClass, setNextClass] = useState(null);
  const [error, setError] = useState("");
  const [departments, setDepartments] = useState([]);
  const [profile, setProfile] = useState({
    department_id: user?.department_id ?? "",
    semester: user?.semester ?? "",
    section: user?.section ?? "",
  });
  const [profileRequired, setProfileRequired] = useState(false);
  const [saving, setSaving] = useState(false);
  const loadSchedule = () => Promise.all([api.get("/timetable"), api.get("/timetable/next-class")])
    .then(([schedule, next]) => {
      setEntries(schedule.data);
      setNextClass(next.data.next_class);
      setProfileRequired(false);
      setError("");
    });
  useEffect(() => {
    loadSchedule().catch((requestError) => {
      if (requestError.response?.status === 422) {
        setError("");
        setProfileRequired(true);
        api.get("/campus/departments").then(({ data }) => setDepartments(data))
          .catch((departmentError) => setError(messageFromError(departmentError)));
      } else {
        setError(messageFromError(requestError));
      }
    });
  }, []);
  const saveProfile = async (event) => {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const { data } = await api.patch("/auth/me/profile", {
        department_id: Number(profile.department_id),
        semester: Number(profile.semester),
        section: profile.section.trim(),
      });
      setUser(data);
      await loadSchedule();
    } catch (requestError) {
      setError(messageFromError(requestError));
    } finally {
      setSaving(false);
    }
  };
  return <div className="page">
    <header className="page-header"><div><p className="eyebrow">YOUR WEEK</p><h1>My timetable</h1>
      <p className="muted">Schedule based on your academic profile.</p></div></header>
    {error && <p className="error" role="alert">{error}</p>}
    {profileRequired ? <form className="card form-card profile-form" onSubmit={saveProfile}>
      <h2>Set up your academic profile</h2>
      <p className="muted">We need these details to retrieve your section's published timetable.</p>
      <label>Department<select required value={profile.department_id}
        onChange={(event) => setProfile({ ...profile, department_id: event.target.value })}>
        <option value="">Choose your department</option>
        {departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
      </select></label>
      <label>Semester<input type="number" required min="1" max="12" value={profile.semester}
        onChange={(event) => setProfile({ ...profile, semester: event.target.value })} /></label>
      <label>Section<input required maxLength="24" value={profile.section}
        onChange={(event) => setProfile({ ...profile, section: event.target.value })} /></label>
      <button className="button button-primary" disabled={saving || !departments.length}>
        {saving ? "Saving…" : "Save academic profile"}
      </button>
      {!departments.length && <p className="footnote">Departments have not been configured by an administrator yet.</p>}
    </form>
      : entries.length ? <>
        {nextClass && <div className="route-summary">
          <strong>Next class: {nextClass.subject}</strong>
          <p>{new Date(nextClass.starts_at).toLocaleString()}
            {nextClass.location && ` · ${nextClass.location}`}
            {nextClass.faculty && ` · ${nextClass.faculty}`}
          </p>
        </div>}
        <div className="schedule-list">{entries.map((entry) => <article className="card schedule-row" key={entry.id}>
          <span className="schedule-day">{weekdays[entry.weekday] ?? `Day ${entry.weekday}`}</span>
          <strong>{entry.starts_at}–{entry.ends_at}</strong><span>{entry.subject}</span>
          {entry.location && <span>{entry.location}</span>}
        </article>)}</div>
      </> : <div className="empty-state">No timetable entries are available for your profile yet.</div>}
  </div>;
}
