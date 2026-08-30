import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Sidebar from "./components/Sidebar";
import EveningLoginScene from "./components/EveningLoginScene";
import FeedbackCat from "./components/FeedbackCat";
import SpeedLoader from "./components/SpeedLoader";
import { API_URL } from "./lib/api";
import "./styles.css";
import "./experience.css";

const API = API_URL;
const labels = {
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
  OPEN: "open",
  UNDER_REVIEW: "review",
  CORRECTED: "corrected",
  AUTO_RESOLVED: "corrected",
  REJECTED: "rejected",
  CORRECTION_REQUESTED: "correction-requested",
};
function hasSafeAiSuggestion(response) {
  return Boolean(
    response?.suggested_field &&
      response.suggested_value !== null &&
      response.suggested_value !== undefined &&
      response.suggested_value !== "",
  );
}
function extractErrorText(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(extractErrorText).filter(Boolean).join("; ");
  if (value && typeof value === "object") {
    if (typeof value.msg === "string") return value.msg;
    for (const key of ["message", "error", "detail"]) {
      const text = extractErrorText(value[key]);
      if (text) return text;
    }
  }
  return "";
}
function getApiError(payload, status, path) {
  if (status === 401) return path === "/auth/login" ? extractErrorText(payload) || "Incorrect email or password." : "Your session has expired. Please sign in again.";
  if (status === 403) return "You do not have permission for this action.";
  if (status === 404) return extractErrorText(payload) || "Requested data was not found.";
  if (status === 409) return extractErrorText(payload) || "This action conflicts with existing data.";
  if (status === 413) return "The selected file is too large.";
  if (status === 422) return extractErrorText(payload?.detail) || "Please check the entered information.";
  if (status === 429) return "Too many requests. Please wait and try again.";
  if (status >= 500) return "The server could not complete the request. Please try again.";
  return extractErrorText(payload) || "The request could not be completed.";
}
function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [user, setUser] = useState(
    JSON.parse(localStorage.getItem("user") || "null"),
  );
  const [view, setView] = useState("dashboard");
  const [message, setMessage] = useState("");
  const [data, setData] = useState({});
  const [uploadResult, setUploadResult] = useState(null);
  const [signingOut, setSigningOut] = useState(false);
  const api = async (path, options = {}) => {
    let res;
    try {
      res = await fetch(`${API}/api${path}`, {
        ...options,
        headers: {
          ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
    } catch {
      throw new Error("Cannot reach the server. Check your connection and try again.");
    }
    const payload = await (res.headers.get("content-type")?.includes("json")
      ? res.json()
      : res.text());
    if (!res.ok) throw new Error(getApiError(payload, res.status, path));
    return payload;
  };
  const load = async (name, path) => {
    try {
      const result = await api(path);
      setData((d) => ({ ...d, [name]: result }));
    } catch (e) {
      setMessage(e.message);
    }
  };
  useEffect(() => {
    if (token) {
      load("summary", "/summary");
      load("activity", "/dashboard/activity");
      load("aiStatus", "/ai/status");
    }
  }, [token]);
  const logout = () => {
    if (signingOut) return;
    setSigningOut(true);
    window.setTimeout(() => {
      localStorage.clear();
      setToken("");
      setUser(null);
      setData({});
      setView("dashboard");
      setSigningOut(false);
    }, 450);
  };
  if (!token || !user)
    return (
      <Login
        onLogin={(x) => {
          localStorage.setItem("token", x.access_token);
          localStorage.setItem("user", JSON.stringify(x.user));
          setToken(x.access_token);
          setUser(x.user);
        }}
        api={api}
      />
    );
  const nav =
    user.role === "DATA_OPERATOR"
      ? ["dashboard", "upload", "batches", "exceptions", "audit"]
      : user.role === "DATA_CONSUMER"
        ? ["dashboard", "batches", "verified", "audit"]
        : ["dashboard", "batches", "exceptions", "verified", "audit"];
  return (
    <div className="app">
      <Sidebar
        user={user}
        nav={nav}
        view={view}
        setView={setView}
        apiUrl={API}
        onLogout={logout}
        signingOut={signingOut}
      />
      {signingOut && <SpeedLoader />}
      <FeedbackCat api={api} />
      <main className="content">
        <header>
          <div>
            <h1>
              {view === "uploadSummary"
                ? "Upload summary"
                : view[0].toUpperCase() + view.slice(1)}
            </h1>
            <p>Human-controlled loan data verification</p>
          </div>
          <div className="user">
            <span className="avatar">{user.name?.[0]}</span>
            {user.name}
          </div>
        </header>
        {message && (
          <div className="notice">
            {message}
            <button onClick={() => setMessage("")}>×</button>
          </div>
        )}
        {view === "dashboard" && (
          <Dashboard
            data={data}
            user={user}
            onNavigate={setView}
            reload={() => {
              load("summary", "/summary");
              load("activity", "/dashboard/activity");
              load("aiStatus", "/ai/status");
            }}
          />
        )}{" "}
        {view === "upload" && (
          <Upload
            api={api}
            onDone={(x) => {
              setUploadResult(x);
              setView("uploadSummary");
            }}
          />
        )}
        {view === "uploadSummary" && (
          <UploadSummary
            result={uploadResult}
            onNext={() => setView("exceptions")}
            onBatch={() => setView("batches")}
          />
        )}{" "}
        {view === "batches" && <BatchRecords api={api} user={user} setMessage={setMessage} />}{" "}
        {view === "exceptions" && (
          <Exceptions api={api} user={user} setMessage={setMessage} />
        )}{" "}
        {view === "verified" && (
          <Verified api={api} token={token} setMessage={setMessage} />
        )}{" "}
        {view === "audit" && <Audit api={api} />}
      </main>
    </div>
  );
}
function Login({ api, onLogin }) {
  const [email, setEmail] = useState("operator@demo.local"),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      onLogin(
        await api("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="login">
      <section className="login-intro">
        <EveningLoginScene />
        <div className="login-intro-copy">
          <h1>Loan Data<br /><em>Verification Copilot</em></h1>
          <p>Turn messy loan tapes into reviewable, AI-assisted, human-approved verified records.</p>
        </div>
      </section>
      <form className="login-card" onSubmit={submit} aria-busy={loading}>
        <h2>Welcome back</h2>
        <p>Use a seeded demo account to begin.</p>
        <label>
          Email
          <input type="email" autoComplete="username" required disabled={loading} value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            minLength={8}
            disabled={loading}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <small className="error" role="alert">{error}</small>}
        <button className="primary login-submit" disabled={loading}>{loading ? "Please wait…" : "Sign in"}</button>
        <small>
          Operator: upload · Reviewer: resolve · Consumer: verify/export
        </small>
      </form>
      {loading && <SpeedLoader message="Verifying secure access…" />}
    </div>
  );
}
function Dashboard({ data, reload, user, onNavigate }) {
  const s = data.summary || {},
    a = data.activity || {},
    ai = data.aiStatus;
  return (
    <>
      <div className="toolbar">
        <button className="secondary" onClick={reload}>
          Refresh data
        </button>
      </div>
      <div className="cards">
        {[
          ["Total loans", s.total_loans],
          ["Exceptions", s.exceptions],
          ["Open review", s.open_exceptions],
          ["Verified", s.verified_loans],
          [
            "Quality score",
            s.quality_score !== undefined ? `${s.quality_score}%` : "—",
          ],
        ].map(([x, b]) => (
          <article key={x}>
            <span>{x}</span>
            <strong>{b ?? "—"}</strong>
          </article>
        ))}
      </div>
      <RoleWorkspace user={user} summary={s} activity={a} onNavigate={onNavigate} />
      <div className="dashboard-grid">
        <section className="panel">
          <h2>AI Review Assistant</h2>
          <p className={ai?.enabled ? "ai-ready" : "ai-offline"}>
            {ai?.enabled ? "● Groq connected" : "● Groq not configured"}
          </p>
          <p className="hint">
            {ai?.enabled
              ? `On-demand model: ${ai.model}`
              : "Add GROQ_API_KEY to backend/.env, then restart FastAPI."}
          </p>
        </section>
        <section className="panel">
          <h2>Exception severity</h2>
          <div className="severity-bars">
            <span>
              <b>High</b>
              <i
                style={{
                  width: `${Math.min(100, (a.severity_breakdown?.HIGH || 0) * 12)}%`,
                }}
              ></i>
              <em>{a.severity_breakdown?.HIGH || 0}</em>
            </span>
            <span>
              <b>Medium</b>
              <i
                className="amber"
                style={{
                  width: `${Math.min(100, (a.severity_breakdown?.MEDIUM || 0) * 12)}%`,
                }}
              ></i>
              <em>{a.severity_breakdown?.MEDIUM || 0}</em>
            </span>
          </div>
        </section>
        <section className="panel">
          <h2>Recent uploads</h2>
          {(a.recent_uploads || []).map((x) => (
            <p className="activity" key={x._id}>
              <b>{x.filename}</b>
              <span>
                {x.rows_success}/{x.rows_total} imported
              </span>
            </p>
          ))}
          {!a.recent_uploads?.length && <p className="hint">No uploads yet.</p>}
        </section>
        <section className="panel">
          <h2>Recent verification</h2>
          {(a.recent_verifications || []).map((x) => (
            <p className="activity" key={x._id}>
              <b>{x.loan_id}</b>
              <span>{x.quality_score}% quality</span>
            </p>
          ))}
          {!a.recent_verifications?.length && (
            <p className="hint">No verified records yet.</p>
          )}
        </section>
      </div>
      <section className="panel">
        <h2>Trust pipeline</h2>
        <div className="pipeline">
          Upload <b>→</b> Normalize <b>→</b> Validate <b>→</b> Review <b>→</b>{" "}
          Verify <b>→</b> Audit
        </div>
        <p>
          Python rules detect issues. Groq explains and recommends. A reviewer
          makes every final decision.
        </p>
      </section>
    </>
  );
}
function RoleWorkspace({ user, summary, activity, onNavigate }) {
  const role = user.role;
  if (role === "DATA_OPERATOR") return <section className="panel role-workspace">
    <div><p className="eyebrow dark">DATA OPERATOR WORKSPACE</p><h2>Ingest and prepare source evidence</h2><p>Upload a loan tape or secondary source, review normalization outcomes, and hand exceptions to the review queue.</p></div>
    <div className="role-metrics"><span><b>{activity.recent_uploads?.length || 0}</b> recent uploads</span><span><b>{summary.open_exceptions ?? 0}</b> records needing review</span></div>
    <div className="actions"><button className="primary" onClick={() => onNavigate("upload")}>Upload source file</button><button className="secondary" onClick={() => onNavigate("batches")}>Inspect normalized batch</button></div>
  </section>;
  if (role === "DATA_CONSUMER") return <section className="panel role-workspace">
    <div><p className="eyebrow dark">DATA CONSUMER WORKSPACE</p><h2>Use trusted, verified loan records</h2><p>Review immutable hashes, the current data-quality score, export verified data, and inspect each loan’s evidence trail.</p></div>
    <div className="role-metrics"><span><b>{summary.verified_loans ?? 0}</b> verified records</span><span><b>{summary.quality_score ?? "—"}%</b> portfolio quality</span></div>
    <div className="actions"><button className="primary" onClick={() => onNavigate("verified")}>Open verified records</button><button className="secondary" onClick={() => onNavigate("audit")}>Inspect audit trail</button></div>
  </section>;
  return <section className="panel role-workspace">
    <div><p className="eyebrow dark">REVIEWER WORKBENCH</p><h2>Resolve exceptions with human control</h2><p>Claim work, compare source evidence, request corrections, and choose whether to use or reject an AI recommendation.</p></div>
    <div className="role-metrics"><span><b>{summary.open_exceptions ?? 0}</b> pending decisions</span><span><b>{activity.severity_breakdown?.CORRECTION_REQUESTED || 0}</b> corrections requested</span></div>
    <div className="actions"><button className="primary" onClick={() => onNavigate("exceptions")}>Open exception queue</button><button className="secondary" onClick={() => onNavigate("batches")}>AI batch workbench</button></div>
  </section>;
}
function Upload({ api, onDone }) {
  const [file, setFile] = useState(),
    [source, setSource] = useState("PRIMARY"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    if (!file) return setError("Choose a CSV file first.");
    setBusy(true);
    try {
      const f = new FormData();
      f.append("file", file);
      const path =
        source === "PRIMARY"
          ? "/uploads"
          : `/uploads/secondary?source_type=${source}`;
      onDone(await api(path, { method: "POST", body: f }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel upload">
      <h2>Upload a source file</h2>
      <p>
        Primary loan tape plus optional servicer and document-manifest sources
        are preserved as evidence.
      </p>
      <form onSubmit={submit}>
        <label>
          Source type
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="PRIMARY">Loan tape</option>
            <option value="SERVICER_UPDATE">Servicer update</option>
            <option value="DOCUMENT_MANIFEST">Document manifest</option>
          </select>
        </label>
        <label className="drop">
          Choose CSV
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files[0])}
          />
          <span>{file?.name || "No file selected"}</span>
        </label>
        {error && <small className="error">{error}</small>}
        <button className="primary" disabled={busy}>
          {busy ? "Importing…" : "Start verification"}
        </button>
      </form>
      <p className="hint">
        Demo files are in the project’s <code>data</code> folder.
      </p>
    </section>
  );
}
function UploadSummary({ result, onNext, onBatch }) {
  if (!result)
    return (
      <section className="panel">
        <p>No upload has been completed in this session.</p>
      </section>
    );
  return (
    <section className="panel summary">
      <p className="eyebrow dark">IMPORT COMPLETE</p>
      <h2>{result.filename}</h2>
      <div className="cards compact">
        {[
          ["Rows received", result.rows_total],
          ["Imported", result.rows_success],
          ["Import failures", result.rows_failed],
          [
            "Rows needing review",
            result.rows_with_exceptions ?? result.conflicts_created ?? 0,
          ],
        ].map(([x, y]) => (
          <article key={x}>
            <span>{x}</span>
            <strong>{y}</strong>
          </article>
        ))}
      </div>
      {result.failed_rows?.length > 0 && (
        <div className="failed">
          <h3>Failed import rows</h3>
          {result.failed_rows.map((x) => (
            <p key={x.row_number}>
              Row {x.row_number}: {x.error}
            </p>
          ))}
        </div>
      )}
      <div className="actions">
        <button className="secondary" onClick={onBatch}>
          View batch records
        </button>
        <button className="primary" onClick={onNext}>
          Open exception queue
        </button>
      </div>
    </section>
  );
}
function BatchRecords({ api, user, setMessage }) {
  const [uploads, setUploads] = useState([]), [uploadId, setUploadId] = useState(""), [result, setResult] = useState(null), [status, setStatus] = useState(""), [search, setSearch] = useState(""), [page, setPage] = useState(0), [busy, setBusy] = useState(false), [batchExceptions, setBatchExceptions] = useState([]), [batchSummary, setBatchSummary] = useState(""), [ruleText, setRuleText] = useState(""), [ruleProposal, setRuleProposal] = useState(""), [aiBusy, setAiBusy] = useState(false);
  const limit = 8;
  const canUseAi = user.role === "REVIEWER" || user.role === "ADMIN";
  const selectedUpload = uploads.find((upload) => upload._id === uploadId);
  const isSecondaryUpload = ["SERVICER_UPDATE", "DOCUMENT_MANIFEST"].includes(selectedUpload?.source_type);
  const isSourceEvidence = result?.record_kind === "SOURCE_EVIDENCE";

  const loadUploads = async () => {
    try { const rows = await api("/uploads"); setUploads(rows); if (!uploadId && rows[0]?._id) setUploadId(rows[0]._id); }
    catch (e) { setMessage(e.message); }
  };
  const loadRecords = async () => {
    if (!uploadId) return;
    setBusy(true);
    try {
      const query = new URLSearchParams({ limit: String(limit), offset: String(page * limit) });
      if (status && !isSecondaryUpload) query.set("status", status);
      if (search) query.set("search", search);
      setResult(await api(`/uploads/${uploadId}/records?${query.toString()}`));
    } catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  };
  const loadBatchExceptions = async () => {
    if (!canUseAi || !uploadId) return;
    try { setBatchExceptions(await api(`/uploads/${uploadId}/exceptions`)); }
    catch (e) { setMessage(e.message); setBatchExceptions([]); }
  };
  const requestBatchSummary = async () => {
    if (!batchExceptions.length) return setMessage("This batch has no open exceptions to summarize.");
    setAiBusy(true);
    try { setBatchSummary(await api("/ai/batch-summary", { method: "POST", body: JSON.stringify({ exception_ids: batchExceptions.map((item) => item._id) }) })); }
    catch (e) { setMessage(e.message); }
    finally { setAiBusy(false); }
  };
  const requestRule = async () => {
    if (ruleText.trim().length < 10) return setMessage("Describe the validation rule in at least 10 characters.");
    setAiBusy(true);
    try { setRuleProposal(await api("/ai/generate-rule", { method: "POST", body: JSON.stringify({ description: ruleText }) })); }
    catch (e) { setMessage(e.message); }
    finally { setAiBusy(false); }
  };
  const verifyReadyLoan = async (loan) => {
    setBusy(true);
    try { await api(`/loans/${encodeURIComponent(loan.loan_id)}/verify`, { method: "POST" }); setMessage(`${loan.loan_id} is now verified. Open the Verified page to inspect or export it.`); await loadRecords(); }
    catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => { loadUploads(); }, []);
  useEffect(() => { loadRecords(); }, [uploadId, status, search, page]);
  useEffect(() => { loadBatchExceptions(); setBatchSummary(""); }, [uploadId, user.role]);

  return <section className="panel batch-records">
    <div className="row"><div><h2>{isSecondaryUpload ? "Batch source evidence" : "Batch loan records"}</h2><p className="hint">{isSecondaryUpload ? "Preserved supporting rows used for source comparison and conflict review." : "Normalized records and their current workflow status."}</p></div><button className="secondary" disabled={busy} onClick={loadRecords}>Refresh</button></div>
    <div className="batch-controls">
      <select value={uploadId} onChange={(e) => { setUploadId(e.target.value); setStatus(""); setPage(0); }}><option value="">Select an upload</option>{uploads.map((upload) => <option key={upload._id} value={upload._id}>{upload.filename} · {upload.rows_success}/{upload.rows_total} rows</option>)}</select>
      {!isSecondaryUpload && <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}><option value="">All statuses</option><option value="READY_FOR_VERIFICATION">Ready for verification</option><option value="NEEDS_REVIEW">Needs review</option><option value="FAILED">Failed</option><option value="VERIFIED">Verified</option></select>}
      <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="Search loan or borrower ID" />
    </div>
    {result?.upload && <p className="hint">{result.upload.filename} · {result.pagination.total} matching {isSourceEvidence ? "source-evidence" : "loan"} records</p>}
    <div className="record-table">
      {isSourceEvidence ? <><div className="record-head"><span>Loan</span><span>Source</span><span>Source row</span><span>Evidence values</span><span>Purpose</span></div>{(result?.items || []).map((source) => <div className="record-item" key={source._id}><b>{source.loan_id || "Missing loan ID"}</b><span>{source.source_type?.replaceAll("_", " ") || "Secondary source"}</span><span>#{source.source_row_number || "—"}</span><span><details><summary>View normalized evidence</summary><code className="source-json">{JSON.stringify(source.raw_row || {}, null, 2)}</code></details></span><span>Preserved for comparison</span></div>)}</> : <><div className="record-head"><span>Loan</span><span>Borrower</span><span>Status</span><span>Source row</span><span>Action</span></div>{(result?.items || []).map((loan) => <div className="record-item" key={loan._id}><b>{loan.loan_id || "Missing loan ID"}</b><span>{loan.borrower_id || "—"}</span><span className={`status ${String(loan.aggregate_status || "NEEDS_REVIEW").toLowerCase()}`}>{String(loan.aggregate_status || "NEEDS_REVIEW").replaceAll("_", " ")}</span><span>#{loan.source_row_number || "—"}</span><span>{canUseAi && loan.aggregate_status === "READY_FOR_VERIFICATION" ? <button className="verify-record" disabled={busy} onClick={() => verifyReadyLoan(loan)}>Verify</button> : "—"}</span></div>)}</>}
    </div>
    {result && !result.items?.length && <p className="hint">No records match this filter.</p>}
    <div className="pagination"><button className="secondary" disabled={page === 0 || busy} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {page + 1}</span><button className="secondary" disabled={!result?.pagination?.has_more || busy} onClick={() => setPage((value) => value + 1)}>Next</button></div>
    {canUseAi && !isSourceEvidence && <section className="ai-workbench">
      <div><p className="eyebrow dark">REVIEWER-ONLY AI WORKBENCH</p><h3>Batch exception summary</h3><p className="hint">Summarize the {batchExceptions.length} open exceptions in this selected batch. AI only recommends; it cannot change records.</p><button className="primary" disabled={aiBusy || !batchExceptions.length} onClick={requestBatchSummary}>{aiBusy ? "Working…" : "Summarize open exceptions"}</button></div>
      {batchSummary && <BatchSummary summary={batchSummary} />}
      <div className="rule-generator"><h3>Ask about a validation rule</h3><p className="hint">Describe an issue you want the system to catch. You can also ask a question; AI will tell you whether a new rule is needed.</p><textarea value={ruleText} onChange={(e) => setRuleText(e.target.value)} placeholder="Example: Flag active loans whose last payment is more than 90 days old." /><div className="rule-examples"><span>Try an example:</span><button type="button" onClick={() => setRuleText("Flag active loans whose last payment is more than 90 days old.")}>Late payment</button><button type="button" onClick={() => setRuleText("Flag loans marked closed when their current balance is greater than zero.")}>Closed loan balance</button><button type="button" onClick={() => setRuleText("Why does this loan need reviewer action?")}>Ask a question</button></div><button className="secondary" disabled={aiBusy} onClick={requestRule}>Get structured guidance</button></div>
      {ruleProposal && <RuleProposal proposal={ruleProposal} />}
    </section>}
  </section>;
}
function BatchSummary({ summary }) {
  const result = summary.summary || {};
  return <section className="batch-summary-result" aria-live="polite">
    <div className="summary-heading"><div><p className="eyebrow dark">AI REVIEW PLAN</p><h3>What needs attention</h3></div><span className={`risk ${String(result.risk_level || "MEDIUM").toLowerCase()}`}>{result.risk_level || "MEDIUM"} PRIORITY</span></div>
    <p className="summary-overview">{result.overall_assessment}</p>
    <div className="summary-meta">Generated by {summary.model} · {summary.created_at ? new Date(summary.created_at).toLocaleString() : "just now"} · {summary.exception_count} open issues reviewed</div>
    <h4>Recommended review order</h4>
    <div className="priority-actions">{(result.priority_actions || []).map((item, index) => <article key={`${item.action}-${index}`}><b>{item.priority || index + 1}</b><div><strong>{item.action}</strong><p>{item.why}</p>{item.affected_loan_ids?.length > 0 && <small>Affected loans: {item.affected_loan_ids.join(", ")}</small>}</div></article>)}</div>
    <h4>Issue groups</h4>
    <div className="issue-groups">{(result.issue_groups || []).map((group, index) => <article key={`${group.issue_type}-${index}`}><div className="issue-title"><strong>{group.issue_type}</strong><span className={`severity-pill ${String(group.severity || "MEDIUM").toLowerCase()}`}>{group.severity}</span></div><p>{group.what_it_means}</p><p><b>Reviewer action:</b> {group.recommended_reviewer_action}</p>{group.affected_loan_ids?.length > 0 && <small>{group.affected_loan_ids.length} loan{group.affected_loan_ids.length === 1 ? "" : "s"}: {group.affected_loan_ids.join(", ")}</small>}</article>)}</div>
    <div className="human-control"><b>Reviewer reminder:</b> {result.reviewer_note}<br /><span>{result.human_control_notice}</span></div>
  </section>;
}
function RuleProposal({ proposal }) {
  const result = proposal.proposal || {};
  const rule = result.proposed_rule;
  const existing = result.existing_rule;
  const heading = rule ? "Proposed validation rule" : existing ? "Already covered by an existing rule" : "Needs more detail";
  const badge = rule ? "RULE PROPOSED" : existing ? "EXISTING RULE" : "CLARIFICATION";
  return <section className="rule-proposal-result" aria-live="polite">
    <div className="summary-heading"><div><p className="eyebrow dark">AI GUIDANCE</p><h3>{heading}</h3></div><span className={`recommendation ${rule ? "yes" : existing ? "covered" : "no"}`}>{badge}</span></div>
    <p className="summary-overview">{result.plain_language_interpretation}</p>
    <div className="summary-meta">Generated by {proposal.model} · {proposal.created_at ? new Date(proposal.created_at).toLocaleString() : "just now"}</div>
    <div className="next-step"><b>Recommended next step:</b> {result.recommended_next_step}</div>
    {(rule || existing) && <><div className="proposed-rule-card"><div><span>Rule name</span><strong>{(rule || existing).name}</strong></div><div><span>Severity</span><strong className={`severity-pill ${String((rule || existing).severity || "MEDIUM").toLowerCase()}`}>{(rule || existing).severity}</strong></div><div><span>{rule ? "Fields checked" : "Rule ID"}</span><strong>{rule ? rule.fields?.join(", ") || "Not specified" : existing.rule_id}</strong></div>{rule && <div><span>Condition</span><strong>{rule.condition}</strong></div>}<p>{(rule || existing).description}</p></div>{rule && <><h4>Suggested test cases</h4><div className="test-cases">{(result.test_cases || []).map((test, index) => <article key={`${test.scenario}-${index}`}><strong>{test.scenario}</strong><p><b>Example:</b> {test.sample_input}</p><p><b>Expected:</b> {test.expected_result}</p></article>)}</div></>}</>}
    <div className="human-control"><b>Before implementation:</b> {result.reviewer_note}<br /><span>This is guidance only. It does not add a rule or change any loan record.</span></div>
  </section>;
}
function Exceptions({ api, user, setMessage }) {
  const [rows, setRows] = useState([]),
    [selected, setSelected] = useState(null),
    [loanDetail, setLoanDetail] = useState(null),
    [filter, setFilter] = useState(""),
    [search, setSearch] = useState(""),
    [ai, setAi] = useState(null),
    [humanDecision, setHumanDecision] = useState(null),
    [comment, setComment] = useState(""),
    [comments, setComments] = useState([]),
    [editValue, setEditValue] = useState(""),
    [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const query = new URLSearchParams();
      if (filter) query.set("severity", filter);
      if (search) query.set("search", search);
      setRows(await api(`/exceptions?${query.toString()}`));
    } catch (e) {
      setMessage(e.message);
    }
  };
  useEffect(() => {
    load();
  }, [filter, search]);
  const choose = async (r) => {
    setSelected(r);
    setAi(null);
    setHumanDecision(null);
    setEditValue("");
    try {
      const [commentRows, detail] = await Promise.all([
        api(`/exceptions/${r._id}/comments`),
        r.loan_id ? api(`/loans/${encodeURIComponent(r.loan_id)}`) : Promise.resolve(null),
      ]);
      setComments(commentRows);
      setLoanDetail(detail);
    } catch {
      setComments([]);
      setLoanDetail(null);
    }
  };
  const act = async (path, body) => {
    setBusy(true);
    try {
      const r = await api(path, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      setMessage("Action saved.");
      await load();
      return r;
    } catch (e) {
      setMessage(e.message);
      return null;
    } finally {
      setBusy(false);
    }
  };
  const submitComment = async () => {
    if (!comment.trim()) return;
    const item = await act(`/exceptions/${selected._id}/comments`, {
      body: comment,
    });
    if (item) {
      setComments((c) => [...c, item]);
      setComment("");
    }
  };
  const chosenField =
    ai?.response?.suggested_field || selected?.affected_fields?.[0] || "";
  const safeAiSuggestion = hasSafeAiSuggestion(ai?.response);
  const isActionable = ["OPEN", "UNDER_REVIEW", "CORRECTION_REQUESTED"].includes(
    selected?.status,
  );
  return (
    <div className="split">
      <section className="panel table">
        <div className="row">
          <h2>Exception queue</h2>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All severities</option>
            <option>HIGH</option>
            <option>MEDIUM</option>
          </select>
        </div>
        <input
          className="search"
          placeholder="Search by loan ID"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {rows.map((r) => (
          <button
            className={`exception ${selected?._id === r._id ? "selected" : ""}`}
            onClick={() => choose(r)}
            key={r._id}
          >
            <span>
              <b>{r.loan_id || "Missing ID"}</b>
              <small>{r.title}</small>
            </span>
            <i className={labels[r.severity]}>{r.severity}</i>
            <em className={labels[r.status]}>{r.status.replaceAll("_", " ")}</em>
          </button>
        ))}
        {!rows.length && <p>No exceptions match this filter.</p>}
      </section>
      <section className="panel detail">
        {selected ? (
          <>
            <div className="row">
              <div>
                <p className="eyebrow dark">EXCEPTION REVIEW</p>
                <h2>{selected.title}</h2>
              </div>
              <i className={labels[selected.severity]}>{selected.severity}</i>
            </div>
            <p>{selected.description}</p>
            <div className="facts">
              <span>
                <b>Loan</b>
                {selected.loan_id || "Missing loan ID"}
              </span>
              <span>
                <b>Affected fields</b>
                {selected.affected_fields?.join(", ")}
              </span>
              <span>
                <b>Status</b>
                {selected.status}
              </span>
            </div>
            {loanDetail?.loan && (
              <details className="normalization">
                <summary>View source lineage and normalization</summary>
                <p>
                  The source row is preserved unchanged. Validation and review use the
                  canonical record on the right.
                </p>
                <div className="source-compare">
                  <div>
                    <b>Raw uploaded row</b>
                    <pre>{JSON.stringify(loanDetail.loan.raw_csv_row, null, 2)}</pre>
                  </div>
                  <div>
                    <b>Normalized canonical record</b>
                    <pre>{JSON.stringify(Object.fromEntries(Object.entries(loanDetail.loan).filter(([key]) => !["_id", "raw_csv_row", "normalization_metadata", "upload_id", "created_at", "updated_at"].includes(key))), null, 2)}</pre>
                  </div>
                </div>
                <small>
                  {loanDetail.loan.normalization_metadata?.changes?.length || 0} normalization changes · version {loanDetail.loan.normalization_metadata?.version || "legacy"}
                </small>
              </details>
            )}
            {user.role !== "DATA_OPERATOR" && isActionable && (
              <div className="actions">
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => act(`/exceptions/${selected._id}/claim`)}
                >
                  Claim review
                </button>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={async () =>
                    setAi(await act(`/exceptions/${selected._id}/ai-review`))
                  }
                >
                  Ask Groq AI
                </button>
              </div>
            )}
            {user.role !== "DATA_OPERATOR" && selected && !isActionable && (
              <div className="human-control">
                <b>This exception is resolved.</b> It remains visible as part of
                the audit history; no further AI review or reviewer decision is
                needed.
              </div>
            )}
            {ai && (
              <div className="ai">
                <span>AI RECOMMENDATION · {ai.model}</span>
                <p>{ai.response?.explanation}</p>
                <b>Suggested correction</b>
                {safeAiSuggestion ? (
                  <p>
                    {ai.response.suggested_field}:{" "}
                    <strong>{String(ai.response.suggested_value)}</strong>
                  </p>
                ) : (
                  <p>
                    <strong>No automatic correction suggested.</strong> Confirm
                    the source evidence, then edit the correct field or request
                    a correction from the source-data owner.
                  </p>
                )}
                {ai.source_comparison?.length > 1 && (
                  <div className="source-evidence">
                    <b>Source evidence comparison</b>
                    <div className="source-evidence-grid">
                      {ai.source_comparison.map((source, index) => (
                        <div key={`${source.source_type}-${index}`}>
                          <small>{source.source_type} · row {source.source_row_number || "—"}</small>
                          {Object.entries(source.values || {}).map(([field, value]) => <p key={field}><span>{field}</span>{String(value ?? "—")}</p>)}
                          {source.last_updated_at && <small>Updated: {source.last_updated_at}</small>}
                        </div>
                      ))}
                    </div>
                    {ai.response?.recommended_source && <p><b>Recommended source:</b> {ai.response.recommended_source}</p>}
                    {ai.response?.comparison_reasoning && <p>{ai.response.comparison_reasoning}</p>}
                  </div>
                )}
                <small>
                  Confidence: {ai.response?.confidence} · AI cannot approve or
                  edit this record.
                </small>
                <small>
                  Generated: {ai.created_at ? new Date(ai.created_at).toLocaleString() : "Recorded now"} · Provider: {ai.provider || "groq"}
                </small>
                <details>
                  <summary>View AI prompt metadata</summary>
                  <p>{ai.prompt_summary || "Exception explanation request"}</p>
                  {ai.prompt && <code className="prompt-preview">{ai.prompt}</code>}
                </details>
              </div>
            )}
            {user.role !== "DATA_OPERATOR" && isActionable && (
              <>
                <div className="decision">
                  <h3>Human decision</h3>
                  <button
                    disabled={!ai || !safeAiSuggestion || busy}
                    onClick={async () => {
                      const decision = await act(`/exceptions/${selected._id}/decision`, {
                        decision: "ACCEPT",
                        ai_review_id: ai?._id,
                        comment: "Accepted after reviewer validation.",
                      });
                      if (decision) setHumanDecision(decision);
                    }}
                  >
                    Accept suggestion
                  </button>
                  <button
                    onClick={async () => {
                      const decision = await act(`/exceptions/${selected._id}/decision`, {
                        decision: "REJECT",
                        comment: "Rejected after reviewer validation.",
                      });
                      if (decision) setHumanDecision(decision);
                    }}
                  >
                    Reject
                  </button>
                  <button
                    onClick={async () => {
                      const decision = await act(`/exceptions/${selected._id}/decision`, {
                        decision: "REQUEST_CORRECTION",
                        comment: "Correction requested from the source-data owner.",
                      });
                      if (decision) setHumanDecision(decision);
                    }}
                  >
                    Request correction
                  </button>
                  <div className="edit">
                    <input
                      value={editValue}
                      placeholder={`Edit ${chosenField}`}
                      onChange={(e) => setEditValue(e.target.value)}
                    />
                    <button
                      onClick={async () => {
                        const decision = await act(`/exceptions/${selected._id}/decision`, {
                          decision: "EDIT",
                          field: chosenField,
                          final_value: isNaN(Number(editValue))
                            ? editValue
                            : Number(editValue),
                          comment: "Reviewer entered a manual correction.",
                        });
                        if (decision) setHumanDecision(decision);
                      }}
                    >
                      Save edit
                    </button>
                  </div>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => act(`/exceptions/${selected._id}/verify`)}
                  >
                    Create verified record
                  </button>
                </div>
                {humanDecision && (
                  <div className="human-decision">
                    <span>FINAL HUMAN DECISION · {humanDecision.decision}</span>
                    <p>
                      {humanDecision.decision === "REJECT"
                        ? "The reviewer rejected this exception."
                        : humanDecision.decision === "REQUEST_CORRECTION"
                          ? "The reviewer requested a correction from the source-data owner. Verification remains blocked until it is resolved."
                        : `${humanDecision.field} was set to ${String(humanDecision.final_value)} by the reviewer.`}
                    </p>
                    {humanDecision.post_edit_validation && (
                      <p className="revalidation-result">
                        Revalidation: <b>{humanDecision.post_edit_validation.aggregate_status.replaceAll("_", " ")}</b>
                        {humanDecision.post_edit_validation.failed_rules?.length
                          ? ` · remaining rules: ${humanDecision.post_edit_validation.failed_rules.join(", ")}`
                          : " · all deterministic checks now pass."}
                      </p>
                    )}
                    <small>This decision, reviewer comment, and any linked AI recommendation are in the audit trail.</small>
                  </div>
                )}
                <div className="comments">
                  <h3>Reviewer notes</h3>
                  {comments.map((c) => (
                    <p key={c._id}>
                      <b>Reviewer</b> · {c.body}
                    </p>
                  ))}
                  <div className="comment">
                    <input
                      placeholder="Add reviewer note"
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                    />
                    <button onClick={submitComment}>Add note</button>
                  </div>
                </div>
              </>
            )}
          </>
        ) : (
          <p>Select an exception to review.</p>
        )}
      </section>
    </div>
  );
}
function Verified({ api, token, setMessage }) {
  const [rows, setRows] = useState([]);
  const load = () =>
    api("/verified-records")
      .then(setRows)
      .catch((e) => setMessage(e.message));
  useEffect(() => {
    load();
  }, []);
  const download = async () => {
    try {
      const r = await fetch(`${API}/api/verified-records/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error("Export failed");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await r.blob());
      a.download = "verified_loans.csv";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setMessage(e.message);
    }
  };
  return (
    <section className="panel table">
      <div className="row">
        <div>
          <h2>Verified records</h2>
          <p className="hint">
            Canonical loan snapshots with immutable hashes.
          </p>
        </div>
        <div className="actions">
          <button className="secondary" onClick={load}>
            Refresh
          </button>
          <button className="primary" onClick={download}>
            Export CSV
          </button>
        </div>
      </div>
      {rows.map((r) => (
        <article className="verified" key={r._id}>
          <b>{r.loan_id}</b>
          <span>Quality {r.quality_score}%</span>
          <code title={r.record_hash}>{r.record_hash}</code>
          <small>{new Date(r.verification_timestamp).toLocaleString()}</small>
        </article>
      ))}
      {!rows.length && <p>No verified records yet.</p>}
    </section>
  );
}
function Audit({ api }) {
  const [id, setId] = useState(""),
    [rows, setRows] = useState([]),
    [error, setError] = useState("");
  const load = async (e) => {
    e.preventDefault();
    try {
      setRows(await api(`/audit/${id}`));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  };
  return (
    <section className="panel">
      <h2>Loan audit trail</h2>
      <form className="inline" onSubmit={load}>
        <input
          placeholder="Loan ID, e.g. LN-10002"
          value={id}
          onChange={(e) => setId(e.target.value)}
        />
        <button className="primary">Open timeline</button>
      </form>
      {error && <p className="error">{error}</p>}
      <ol className="timeline">
        {rows.map((r) => (
          <li key={r._id}>
            <b>{r.event_type}</b>
            <span>{r.action_detail}</span>
            <small>{r.timestamp}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}
createRoot(document.getElementById("root")).render(<App />);
