import { useEffect, useState } from "react";
import { api, messageFromError } from "../api/client";

export default function LostFound() {
  const [form, setForm] = useState({ report_type: "LOST", description: "", location: "", occurred_at: "" });
  const [image, setImage] = useState(null);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reports, setReports] = useState([]);
  const loadReports = async () => {
    try {
      const { data } = await api.get("/lost-found/reports");
      setReports(data);
    } catch (requestError) {
      setError(messageFromError(requestError));
    }
  };
  useEffect(() => { loadReports(); }, []);
  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setResult("");
    setBusy(true);
    try {
      const { data } = await api.post("/lost-found/reports", {
        ...form,
        occurred_at: form.occurred_at ? new Date(form.occurred_at).toISOString() : null,
      });
      let imageError = "";
      if (image) {
        const body = new FormData();
        body.append("file", image);
        try {
          await api.post(`/lost-found/reports/${data.id}/images`, body);
        } catch (requestError) {
          imageError = ` The report was saved, but the photo could not be uploaded: ${messageFromError(requestError)}`;
        }
      }
      setResult(`Report submitted. Your tracking ID is ${data.report_code}.${imageError}`);
      setForm({ report_type: "LOST", description: "", location: "", occurred_at: "" });
      setImage(null);
      event.target.reset();
      await loadReports();
    } catch (requestError) {
      setError(messageFromError(requestError));
    } finally {
      setBusy(false);
    }
  };
  return <div className="page narrow-page">
    <header className="page-header"><div><p className="eyebrow">CAMPUS COMMUNITY</p><h1>Lost & Found</h1>
      <p className="muted">Tell the campus team about an item you lost or found.</p></div></header>
    <form className="card form-card" onSubmit={submit}>
      <label>Report type<select value={form.report_type} onChange={(e) => setForm({ ...form, report_type: e.target.value })}>
        <option value="LOST">I lost an item</option><option value="FOUND">I found an item</option>
      </select></label>
      <label>Item description<textarea required minLength={3} maxLength={4000} rows={4} value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Describe the item, including identifying details." /></label>
      <label>Where was it lost or found?<input required minLength={2} maxLength={200} value={form.location}
        onChange={(e) => setForm({ ...form, location: e.target.value })} /></label>
      <label>Date and time (optional)<input type="datetime-local" value={form.occurred_at}
        onChange={(e) => setForm({ ...form, occurred_at: e.target.value })} /></label>
      <label>Photo (optional, max 5 MB)<input type="file" accept="image/jpeg,image/png,image/webp"
        onChange={(e) => setImage(e.target.files?.[0] ?? null)} /></label>
      {error && <p className="error" role="alert">{error}</p>}
      {result && <p className="success" role="status">{result}</p>}
      <button className="button button-primary" disabled={busy}>{busy ? "Submitting…" : "Submit report"}</button>
      <p className="footnote">Only authorized staff can review reports. Your report details are visible to you and campus administrators.</p>
    </form>
    <section className="section">
      <div className="section-heading"><h2>Your reports</h2><span className="muted">Private to your account</span></div>
      {reports.length ? <div className="admin-list">{reports.map((report) => <article className="card admin-report" key={report.id}>
        <div><p className="eyebrow">{report.report_code} · {report.report_type}</p><h2>{report.description}</h2>
          <p className="muted">{report.location} · {new Date(report.created_at).toLocaleString()}</p></div>
        <strong className="status-label">{report.status.replaceAll("_", " ")}</strong>
      </article>)}</div> : <p className="empty-state">You have not submitted a report yet.</p>}
    </section>
  </div>;
}
