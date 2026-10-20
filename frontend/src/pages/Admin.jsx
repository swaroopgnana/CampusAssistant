import { useEffect, useState } from "react";
import { api, messageFromError } from "../api/client";

const statuses = ["SUBMITTED", "UNDER_REVIEW", "MATCHED", "READY_FOR_COLLECTION", "RESOLVED"];
const emptyEvent = {
  title: "", description: "", starts_at: "", ends_at: "", location_id: "",
  organizer: "", registration_url: "", registration_required: false, published: false,
};
const emptyNews = { title: "", category: "Announcement", description: "", source: "", published: false };
const emptyDocument = { title: "", source: "", content: "" };
const emptyLocation = { name: "", latitude: "", longitude: "", description: "" };
const emptyPath = { from_location_id: "", to_location_id: "", distance_meters: "", accessible: true };
const emptyDepartment = { name: "" };
const emptySubject = { code: "", name: "" };
const emptySection = { department_id: "", semester: "", section: "" };
const emptyClass = {
  department_id: "", semester: "", section: "", subject_id: "",
  weekday: "0", starts_at: "", ends_at: "", location_id: "",
};

function ReportImage({ reportId, imageId }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let objectUrl;
    api.get(`/admin/lost-found/reports/${reportId}/images/${imageId}`, { responseType: "blob" })
      .then(({ data }) => {
        objectUrl = URL.createObjectURL(data);
        setUrl(objectUrl);
      }).catch(() => setUrl(""));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [reportId, imageId]);
  return url ? <img className="report-image" src={url} alt={`Photo attached to ${reportId}`} /> : null;
}

export default function Admin() {
  const [overview, setOverview] = useState(null);
  const [reports, setReports] = useState([]);
  const [events, setEvents] = useState([]);
  const [news, setNews] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [users, setUsers] = useState([]);
  const [locations, setLocations] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [sections, setSections] = useState([]);
  const [paths, setPaths] = useState([]);
  const [timetable, setTimetable] = useState([]);
  const [collegeTimezone, setCollegeTimezone] = useState("");
  const [eventForm, setEventForm] = useState(emptyEvent);
  const [newsForm, setNewsForm] = useState(emptyNews);
  const [documentForm, setDocumentForm] = useState(emptyDocument);
  const [locationForm, setLocationForm] = useState(emptyLocation);
  const [pathForm, setPathForm] = useState(emptyPath);
  const [departmentForm, setDepartmentForm] = useState(emptyDepartment);
  const [subjectForm, setSubjectForm] = useState(emptySubject);
  const [sectionForm, setSectionForm] = useState(emptySection);
  const [classForm, setClassForm] = useState(emptyClass);
  const [reportStatus, setReportStatus] = useState("");
  const [reportType, setReportType] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const [overviewResult, reportResult, eventResult, newsResult, documentResult, userResult,
        locationResult, departmentResult, subjectResult, sectionResult, pathResult, timetableResult, configResult] =
        await Promise.all([
          api.get("/admin/overview"),
          api.get("/admin/lost-found/reports", { params: {
            status_filter: reportStatus || undefined,
            type_filter: reportType || undefined,
          } }),
          api.get("/admin/events"),
          api.get("/admin/news"),
          api.get("/admin/knowledge-documents"),
          api.get("/admin/users"),
          api.get("/campus/locations"),
          api.get("/campus/departments"),
          api.get("/campus/subjects"),
          api.get("/admin/academic-sections"),
          api.get("/admin/campus/paths"),
          api.get("/admin/timetable"),
          api.get("/campus/config"),
        ]);
      setOverview(overviewResult.data);
      setReports(reportResult.data);
      setEvents(eventResult.data);
      setNews(newsResult.data);
      setDocuments(documentResult.data);
      setUsers(userResult.data);
      setLocations(locationResult.data);
      setDepartments(departmentResult.data);
      setSubjects(subjectResult.data);
      setSections(sectionResult.data);
      setPaths(pathResult.data);
      setTimetable(timetableResult.data);
      setCollegeTimezone(configResult.data.timezone);
      setError("");
    } catch (requestError) {
      setError(messageFromError(requestError));
    }
  };
  useEffect(() => { load(); }, [reportStatus, reportType]);
  const showFailure = (requestError) => {
    setSuccess("");
    setError(messageFromError(requestError));
  };
  const update = async (reportId, status) => {
    try {
      await api.patch(`/admin/lost-found/reports/${reportId}`, { status });
      await load();
    } catch (requestError) {
      showFailure(requestError);
    }
  };
  const submitEvent = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/admin/events", {
        ...eventForm,
        ends_at: eventForm.ends_at || null,
        location_id: eventForm.location_id ? Number(eventForm.location_id) : null,
      });
      setEventForm(emptyEvent);
      setSuccess("Event created.");
      await load();
    } catch (requestError) {
      showFailure(requestError);
    } finally {
      setBusy(false);
    }
  };
  const submitNews = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/admin/news", newsForm);
      setNewsForm(emptyNews);
      setSuccess("News item created.");
      await load();
    } catch (requestError) {
      showFailure(requestError);
    } finally {
      setBusy(false);
    }
  };
  const submitDocument = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/admin/knowledge-documents", documentForm);
      setDocumentForm(emptyDocument);
      setSuccess("Document added for review. It will not be used by the assistant until approved.");
      await load();
    } catch (requestError) {
      showFailure(requestError);
    } finally {
      setBusy(false);
    }
  };
  const updateEvent = async (eventId, values) => {
    try {
      await api.patch(`/admin/events/${eventId}`, values);
      await load();
    } catch (requestError) {
      showFailure(requestError);
    }
  };
  const updateNews = async (newsId, published) => {
    try {
      await api.patch(`/admin/news/${newsId}`, { published });
      await load();
    } catch (requestError) {
      showFailure(requestError);
    }
  };
  const approveDocument = async (documentId) => {
    try {
      await api.patch(`/admin/knowledge-documents/${documentId}/approve`);
      setSuccess("Knowledge document approved.");
      await load();
    } catch (requestError) {
      showFailure(requestError);
    }
  };
  const updateRole = async (userId, role) => {
    try {
      await api.patch(`/admin/users/${userId}/role`, { role });
      await load();
    } catch (requestError) {
      showFailure(requestError);
    }
  };
  const createRecord = async (path, payload, reset, successMessage) => {
    setBusy(true);
    setError("");
    try {
      await api.post(path, payload);
      reset();
      setSuccess(successMessage);
      await load();
    } catch (requestError) {
      showFailure(requestError);
    } finally {
      setBusy(false);
    }
  };
  return <div className="page">
    <header className="page-header"><div><p className="eyebrow">STAFF WORKSPACE</p><h1>Admin dashboard</h1>
      <p className="muted">Manage verified campus information and student reports.</p></div></header>
    {error && <p className="error" role="alert">{error}</p>}
    {success && <p className="success" role="status">{success}</p>}
    <section className="stats-grid">
      {Object.entries({ Users: overview?.users, Events: overview?.events, News: overview?.news, "Open reports": overview?.open_reports })
        .map(([label, value]) => <article className="card stat-card" key={label}>
          <span className="muted">{label}</span><strong>{value ?? "—"}</strong>
        </article>)}
    </section>
    <section className="section admin-section">
      <div className="section-heading"><h2>Campus and academic data</h2><span className="muted">Add verified records before student lookups</span></div>
      <div className="admin-resource-grid">
        <form className="card admin-form" onSubmit={(e) => {
          e.preventDefault();
          createRecord("/admin/departments", departmentForm, () => setDepartmentForm(emptyDepartment), "Department added.");
        }}>
          <h3>Department</h3>
          <label>Name<input required maxLength="160" value={departmentForm.name}
            onChange={(e) => setDepartmentForm({ name: e.target.value })} /></label>
          <button className="button button-primary" disabled={busy}>Add department</button>
        </form>
        <form className="card admin-form" onSubmit={(e) => {
          e.preventDefault();
          createRecord("/admin/subjects", subjectForm, () => setSubjectForm(emptySubject), "Subject added.");
        }}>
          <h3>Subject</h3>
          <label>Code<input required maxLength="32" value={subjectForm.code}
            onChange={(e) => setSubjectForm({ ...subjectForm, code: e.target.value })} /></label>
          <label>Name<input required maxLength="160" value={subjectForm.name}
            onChange={(e) => setSubjectForm({ ...subjectForm, name: e.target.value })} /></label>
          <button className="button button-primary" disabled={busy}>Add subject</button>
        </form>
        <form className="card admin-form" onSubmit={(e) => {
          e.preventDefault();
          createRecord("/admin/campus/locations", {
            ...locationForm,
            latitude: locationForm.latitude === "" ? null : Number(locationForm.latitude),
            longitude: locationForm.longitude === "" ? null : Number(locationForm.longitude),
          }, () => setLocationForm(emptyLocation), "Campus location added.");
        }}>
          <h3>Campus location</h3>
          <label>Name<input required maxLength="160" value={locationForm.name}
            onChange={(e) => setLocationForm({ ...locationForm, name: e.target.value })} /></label>
          <div className="form-row">
            <label>Latitude<input type="number" min="-90" max="90" step="any" value={locationForm.latitude}
              onChange={(e) => setLocationForm({ ...locationForm, latitude: e.target.value })} /></label>
            <label>Longitude<input type="number" min="-180" max="180" step="any" value={locationForm.longitude}
              onChange={(e) => setLocationForm({ ...locationForm, longitude: e.target.value })} /></label>
          </div>
          <label>Description<textarea rows="2" value={locationForm.description}
            onChange={(e) => setLocationForm({ ...locationForm, description: e.target.value })} /></label>
          <button className="button button-primary" disabled={busy}>Add location</button>
        </form>
        <form className="card admin-form" onSubmit={(e) => {
          e.preventDefault();
          createRecord("/admin/academic-sections", {
            ...sectionForm,
            department_id: Number(sectionForm.department_id),
            semester: Number(sectionForm.semester),
            section: sectionForm.section.trim().toUpperCase(),
          }, () => setSectionForm(emptySection), "Academic section added.");
        }}>
          <h3>Academic section</h3>
          <label>Department<select required value={sectionForm.department_id}
            onChange={(e) => setSectionForm({ ...sectionForm, department_id: e.target.value })}>
            <option value="">Choose department</option>{departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select></label>
          <div className="form-row">
            <label>Semester<input required type="number" min="1" max="12" value={sectionForm.semester}
              onChange={(e) => setSectionForm({ ...sectionForm, semester: e.target.value })} /></label>
            <label>Section<input required maxLength="24" value={sectionForm.section}
              onChange={(e) => setSectionForm({ ...sectionForm, section: e.target.value })} /></label>
          </div>
          <button className="button button-primary" disabled={busy || !departments.length}>Add section</button>
        </form>
        <form className="card admin-form" onSubmit={(e) => {
          e.preventDefault();
          createRecord("/admin/campus/paths", {
            ...pathForm,
            from_location_id: Number(pathForm.from_location_id),
            to_location_id: Number(pathForm.to_location_id),
            distance_meters: Number(pathForm.distance_meters),
          }, () => setPathForm(emptyPath), "Campus pathway added.");
        }}>
          <h3>Mapped pathway</h3>
          <label>From<select required value={pathForm.from_location_id}
            onChange={(e) => setPathForm({ ...pathForm, from_location_id: e.target.value })}>
            <option value="">Choose origin</option>{locations.map((loc) => <option key={loc.id} value={loc.id}>{loc.name}</option>)}
          </select></label>
          <label>To<select required value={pathForm.to_location_id}
            onChange={(e) => setPathForm({ ...pathForm, to_location_id: e.target.value })}>
            <option value="">Choose destination</option>{locations.map((loc) => <option key={loc.id} value={loc.id}>{loc.name}</option>)}
          </select></label>
          <label>Path length (meters)<input required type="number" min="1" value={pathForm.distance_meters}
            onChange={(e) => setPathForm({ ...pathForm, distance_meters: e.target.value })} /></label>
          <label className="checkbox-label"><input type="checkbox" checked={pathForm.accessible}
            onChange={(e) => setPathForm({ ...pathForm, accessible: e.target.checked })} /> Wheelchair accessible</label>
          <button className="button button-primary" disabled={busy || locations.length < 2}>Add pathway</button>
        </form>
        <form className="card admin-form" onSubmit={(e) => {
          e.preventDefault();
          createRecord("/admin/timetable", {
            ...classForm,
            department_id: Number(classForm.department_id),
            semester: Number(classForm.semester),
            subject_id: Number(classForm.subject_id),
            weekday: Number(classForm.weekday),
            location_id: classForm.location_id ? Number(classForm.location_id) : null,
            section: classForm.section.trim().toUpperCase(),
          }, () => setClassForm(emptyClass), "Timetable entry added.");
        }}>
          <h3>Timetable entry</h3>
          <label>Department<select required value={classForm.department_id}
            onChange={(e) => setClassForm({ ...classForm, department_id: e.target.value })}>
            <option value="">Choose department</option>{departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select></label>
          <div className="form-row">
            <label>Semester<input required type="number" min="1" max="12" value={classForm.semester}
              onChange={(e) => setClassForm({ ...classForm, semester: e.target.value })} /></label>
            <label>Section<input required maxLength="24" value={classForm.section}
              onChange={(e) => setClassForm({ ...classForm, section: e.target.value })} /></label>
          </div>
          <label>Subject<select required value={classForm.subject_id}
            onChange={(e) => setClassForm({ ...classForm, subject_id: e.target.value })}>
            <option value="">Choose subject</option>{subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.code} · {subject.name}</option>)}
          </select></label>
          <div className="form-row">
            <label>Day<select value={classForm.weekday} onChange={(e) => setClassForm({ ...classForm, weekday: e.target.value })}>
              {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((day, index) =>
                <option key={day} value={index}>{day}</option>)}
            </select></label>
            <label>Location<select value={classForm.location_id}
              onChange={(e) => setClassForm({ ...classForm, location_id: e.target.value })}>
              <option value="">Not specified</option>{locations.map((loc) => <option key={loc.id} value={loc.id}>{loc.name}</option>)}
            </select></label>
          </div>
          <div className="form-row">
            <label>Starts<input required type="time" value={classForm.starts_at}
              onChange={(e) => setClassForm({ ...classForm, starts_at: e.target.value })} /></label>
            <label>Ends<input required type="time" value={classForm.ends_at}
              onChange={(e) => setClassForm({ ...classForm, ends_at: e.target.value })} /></label>
          </div>
          <button className="button button-primary" disabled={busy || !departments.length || !subjects.length}>Add class</button>
        </form>
      </div>
      <div className="admin-data-summary">
        <p><strong>Locations:</strong> {locations.map((item) => item.name).join(", ") || "None configured"}</p>
        <p><strong>Sections:</strong> {sections.map((item) => `${item.department} · Sem ${item.semester} · ${item.section}`).join(" / ") || "None configured"}</p>
        <p><strong>Pathways:</strong> {paths.map((item) => `${item.from_location} → ${item.to_location} (${item.distance_meters} m)`).join(" / ") || "None configured"}</p>
        <p><strong>Timetable entries:</strong> {timetable.length}</p>
      </div>
    </section>
    <section className="section admin-section">
      <div className="section-heading"><h2>Events</h2><span className="muted">Published updates are visible to students</span></div>
      <form className="card admin-form" onSubmit={submitEvent}>
        <label>Event name<input required maxLength="200" value={eventForm.title}
          onChange={(e) => setEventForm({ ...eventForm, title: e.target.value })} /></label>
        <label>Description<textarea rows="2" value={eventForm.description}
          onChange={(e) => setEventForm({ ...eventForm, description: e.target.value })} /></label>
        <div className="form-row">
          <label>Starts at ({collegeTimezone || "college time"})<input required type="datetime-local" value={eventForm.starts_at}
            onChange={(e) => setEventForm({ ...eventForm, starts_at: e.target.value })} /></label>
          <label>Ends at ({collegeTimezone || "college time"})<input type="datetime-local" value={eventForm.ends_at}
            onChange={(e) => setEventForm({ ...eventForm, ends_at: e.target.value })} /></label>
        </div>
        <div className="form-row">
          <label>Location<select value={eventForm.location_id}
            onChange={(e) => setEventForm({ ...eventForm, location_id: e.target.value })}>
            <option value="">Not specified</option>
            {locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}
          </select></label>
          <label>Organizer<input maxLength="160" value={eventForm.organizer}
            onChange={(e) => setEventForm({ ...eventForm, organizer: e.target.value })} /></label>
        </div>
        <label>Registration link (optional)<input type="url" value={eventForm.registration_url}
          onChange={(e) => setEventForm({ ...eventForm, registration_url: e.target.value })} /></label>
        <label className="checkbox-label"><input type="checkbox" checked={eventForm.registration_required}
          onChange={(e) => setEventForm({ ...eventForm, registration_required: e.target.checked })} /> Registration required</label>
        <label className="checkbox-label"><input type="checkbox" checked={eventForm.published}
          onChange={(e) => setEventForm({ ...eventForm, published: e.target.checked })} /> Publish immediately</label>
        <button className="button button-primary" disabled={busy}>{busy ? "Saving…" : "Create event"}</button>
      </form>
      <div className="admin-list">{events.map((event) => <article className="card admin-report" key={event.id}>
        <div><p className="eyebrow">{event.published ? "PUBLISHED" : "DRAFT"}{event.cancelled ? " · CANCELLED" : ""}</p>
          <h2>{event.title}</h2><p className="muted">
            {new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: event.timezone })
              .format(new Date(event.starts_at))} · {event.location ?? "Location not set"}
          </p></div>
        <div className="admin-actions">
          <label>Visibility<select value={event.published ? "published" : "draft"}
            onChange={(e) => updateEvent(event.id, { published: e.target.value === "published" })}>
            <option value="draft">Draft</option><option value="published">Published</option>
          </select></label>
          {!event.cancelled && <button className="button button-quiet" onClick={() => updateEvent(event.id, { cancelled: true })}>Cancel event</button>}
        </div>
      </article>)}</div>
    </section>
    <section className="section admin-section">
      <div className="section-heading"><h2>College news</h2><span className="muted">Only approved sources should be published</span></div>
      <form className="card admin-form" onSubmit={submitNews}>
        <label>Headline<input required maxLength="200" value={newsForm.title}
          onChange={(e) => setNewsForm({ ...newsForm, title: e.target.value })} /></label>
        <div className="form-row">
          <label>Category<input required maxLength="48" value={newsForm.category}
            onChange={(e) => setNewsForm({ ...newsForm, category: e.target.value })} /></label>
          <label>Source<input required maxLength="200" value={newsForm.source}
            onChange={(e) => setNewsForm({ ...newsForm, source: e.target.value })} /></label>
        </div>
        <label>Description<textarea required rows="3" value={newsForm.description}
          onChange={(e) => setNewsForm({ ...newsForm, description: e.target.value })} /></label>
        <label className="checkbox-label"><input type="checkbox" checked={newsForm.published}
          onChange={(e) => setNewsForm({ ...newsForm, published: e.target.checked })} /> Publish immediately</label>
        <button className="button button-primary" disabled={busy}>{busy ? "Saving…" : "Create news item"}</button>
      </form>
      {news.map((item) => <article className="card admin-row" key={item.id}>
        <div><p className="eyebrow">{item.category} · {item.source}</p><h3>{item.title}</h3></div>
        <label>Visibility<select value={item.published ? "published" : "draft"}
          onChange={(e) => updateNews(item.id, e.target.value === "published")}>
          <option value="draft">Draft</option><option value="published">Published</option>
        </select></label>
      </article>)}
    </section>
    <section className="section admin-section">
      <div className="section-heading"><h2>Knowledge base</h2><span className="muted">Assistant only retrieves approved records</span></div>
      <form className="card admin-form" onSubmit={submitDocument}>
        <label>Document title<input required maxLength="200" value={documentForm.title}
          onChange={(e) => setDocumentForm({ ...documentForm, title: e.target.value })} /></label>
        <label>Verified source<input required maxLength="500" value={documentForm.source}
          onChange={(e) => setDocumentForm({ ...documentForm, source: e.target.value })} /></label>
        <label>Content<textarea required rows="5" value={documentForm.content}
          onChange={(e) => setDocumentForm({ ...documentForm, content: e.target.value })} /></label>
        <button className="button button-primary" disabled={busy}>{busy ? "Saving…" : "Add for review"}</button>
      </form>
      {documents.map((document) => <article className="card admin-row" key={document.id}>
        <div><p className="eyebrow">{document.approved ? "APPROVED" : "NEEDS REVIEW"} · {document.source}</p><h3>{document.title}</h3></div>
        {!document.approved && <button className="button button-primary" onClick={() => approveDocument(document.id)}>Approve</button>}
      </article>)}
    </section>
    <section className="section admin-section">
      <div className="section-heading"><h2>Lost & Found reports</h2><span className="muted">{reports.length} reports</span></div>
      <div className="report-filters">
        <label>Type<select value={reportType} onChange={(e) => setReportType(e.target.value)}>
          <option value="">All reports</option><option value="LOST">Lost</option><option value="FOUND">Found</option>
        </select></label>
        <label>Status<select value={reportStatus} onChange={(e) => setReportStatus(e.target.value)}>
          <option value="">Any status</option>{statuses.map((status) => <option key={status}>{status}</option>)}
        </select></label>
      </div>
      {reports.length ? <div className="admin-list">{reports.map((report) => <article className="card admin-report" key={report.id}>
        <div><p className="eyebrow">{report.report_code} · {report.report_type}</p><h2>{report.description}</h2>
          <p className="muted">{report.location} · {new Date(report.created_at).toLocaleString()}</p>
          <div className="report-images">{report.images?.map((image) =>
            <ReportImage key={image.id} reportId={report.id} imageId={image.id} />)}</div>
        </div>
        <label>Status<select value={report.status} onChange={(event) => update(report.id, event.target.value)}>
          {statuses.map((status) => <option key={status}>{status}</option>)}
        </select></label>
      </article>)}</div> : <p className="empty-state">There are no Lost & Found reports to review.</p>}
    </section>
    <section className="section admin-section">
      <div className="section-heading"><h2>Users and roles</h2><span className="muted">{users.length} accounts</span></div>
      {users.map((account) => <article className="card admin-row" key={account.id}>
        <div><strong>{account.full_name}</strong><p className="muted">{account.email}</p></div>
        <label>Role<select value={account.role} onChange={(event) => updateRole(account.id, event.target.value)}>
          <option value="student">Student</option><option value="faculty">Faculty</option><option value="admin">Admin</option>
        </select></label>
      </article>)}
    </section>
  </div>;
}
