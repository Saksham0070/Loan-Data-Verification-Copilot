import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import AiReviewPanel from "./components/AiReviewPanel";
import Sidebar from "./components/Sidebar";
import { API_URL } from "./lib/api";
import "./styles.css";

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
};
function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [user, setUser] = useState(
    JSON.parse(localStorage.getItem("user") || "null"),
  );
  const [view, setView] = useState("dashboard");
  const [message, setMessage] = useState("");
  const [data, setData] = useState({});
  const [uploadResult, setUploadResult] = useState(null);
  const api = async (path, options = {}) => {
    const res = await fetch(`${API}/api${path}`, {
      ...options,
      headers: {
        ...(options.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    const payload = await (res.headers.get("content-type")?.includes("json")
      ? res.json()
      : res.text());
    if (!res.ok)
      throw new Error(
        typeof payload === "string"
          ? payload
          : payload.detail || "Request failed",
      );
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
    localStorage.clear();
    setToken("");
    setUser(null);
    setData({});
    setView("dashboard");
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
      />
      <main>
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
            api={api}
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
        {view === "batches" && <BatchRecords api={api} setMessage={setMessage} />}{" "}
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
    [password, setPassword] = useState("DemoPass123!"),
    [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try {
      onLogin(
        await api("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }),
      );
    } catch (e) {
      setError(e.message);
    }
  };
  return (
    <div className="login">
      <section>
        <span className="eyebrow">INTAIN CAMPUS FINTECH CHALLENGE</span>
        <h1>
          Loan Data
          <br />
          <em>Verification Copilot</em>
        </h1>
        <p>
          Turn messy loan tapes into reviewable, AI-assisted, human-approved
          verified records.
        </p>
      </section>
      <form onSubmit={submit}>
        <h2>Welcome back</h2>
        <p>Use a seeded demo account to begin.</p>
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <small className="error">{error}</small>}
        <button className="primary">Sign in</button>
        <small>
          Operator: upload · Reviewer: resolve · Consumer: verify/export
        </small>
      </form>
    </div>
  );
}
function Dashboard({ data, reload }) {
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
function BatchRecords({ api, setMessage }) {
  const [uploads, setUploads] = useState([]), [uploadId, setUploadId] = useState(""), [result, setResult] = useState(null), [status, setStatus] = useState(""), [search, setSearch] = useState(""), [page, setPage] = useState(0), [busy, setBusy] = useState(false);
  const limit = 8;
  const loadUploads = async () => {
    try { const rows = await api("/uploads"); setUploads(rows); if (!uploadId && rows[0]?._id) setUploadId(rows[0]._id); }
    catch (e) { setMessage(e.message); }
  };
  const loadRecords = async () => {
    if (!uploadId) return;
    setBusy(true);
    try { const query = new URLSearchParams({ limit: String(limit), offset: String(page * limit) }); if (status) query.set("status", status); if (search) query.set("search", search); setResult(await api(`/uploads/${uploadId}/records?${query.toString()}`)); }
    catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => { loadUploads(); }, []);
  useEffect(() => { loadRecords(); }, [uploadId, status, search, page]);
  return <section className="panel batch-records">
    <div className="row"><div><h2>Batch loan records</h2><p className="hint">Normalized records and their current workflow status.</p></div><button className="secondary" disabled={busy} onClick={loadRecords}>Refresh</button></div>
    <div className="batch-controls">
      <select value={uploadId} onChange={(e) => { setUploadId(e.target.value); setPage(0); }}><option value="">Select an upload</option>{uploads.map((upload) => <option key={upload._id} value={upload._id}>{upload.filename} · {upload.rows_success}/{upload.rows_total} rows</option>)}</select>
      <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}><option value="">All statuses</option><option value="READY_FOR_VERIFICATION">Ready for verification</option><option value="NEEDS_REVIEW">Needs review</option><option value="FAILED">Failed</option><option value="VERIFIED">Verified</option></select>
      <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="Search loan or borrower ID" />
    </div>
    {result?.upload && <p className="hint">{result.upload.filename} · {result.pagination.total} matching records</p>}
    <div className="record-table"><div className="record-head"><span>Loan</span><span>Borrower</span><span>Status</span><span>Source row</span></div>{(result?.items || []).map((loan) => <div className="record-item" key={loan._id}><b>{loan.loan_id || "Missing loan ID"}</b><span>{loan.borrower_id || "—"}</span><span className={`status ${String(loan.aggregate_status || "NEEDS_REVIEW").toLowerCase()}`}>{String(loan.aggregate_status || "NEEDS_REVIEW").replaceAll("_", " ")}</span><span>#{loan.source_row_number || "—"}</span></div>)}</div>
    {result && !result.items?.length && <p className="hint">No records match this filter.</p>}
    <div className="pagination"><button className="secondary" disabled={page === 0 || busy} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {page + 1}</span><button className="secondary" disabled={!result?.pagination?.has_more || busy} onClick={() => setPage((value) => value + 1)}>Next</button></div>
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
            <em className={labels[r.status]}>{r.status}</em>
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
            {user.role !== "DATA_OPERATOR" && (
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
            {ai && (
              <div className="ai">
                <span>AI RECOMMENDATION · {ai.model}</span>
                <p>{ai.response?.explanation}</p>
                <b>Suggested correction</b>
                <p>
                  {ai.response?.suggested_field}:{" "}
                  <strong>{String(ai.response?.suggested_value)}</strong>
                </p>
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
            {user.role !== "DATA_OPERATOR" && (
              <>
                <div className="decision">
                  <h3>Human decision</h3>
                  <button
                    disabled={!ai || busy}
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
