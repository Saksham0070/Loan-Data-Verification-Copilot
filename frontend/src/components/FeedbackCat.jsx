import React, { useEffect, useState } from "react";

export default function FeedbackCat({ api }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [feedback, setFeedback] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = (event) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setStatus("");
    try {
      const result = await api("/feedback", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), feedback: feedback.trim() }),
      });
      setStatus(result.message);
      setName("");
      setFeedback("");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button className="feedback-cat" type="button" aria-label="Share feedback" title="Share feedback" onClick={() => { setOpen(true); setStatus(""); }}>
        <span className="cat-ear cat-ear-left" /><span className="cat-ear cat-ear-right" />
        <span className="cat-eye cat-eye-left" /><span className="cat-eye cat-eye-right" />
        <span className="cat-tail" /><small>feedback?</small>
      </button>
      {open && <div className="feedback-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setOpen(false)}>
        <section className="feedback-dialog" role="dialog" aria-modal="true" aria-labelledby="feedback-title">
          <button className="feedback-close" type="button" aria-label="Close feedback form" onClick={() => setOpen(false)}>×</button>
          <span className="feedback-cat-icon" aria-hidden="true">🐈‍⬛</span>
          <h2 id="feedback-title">Help us improve</h2><p>Just your name and a short thought.</p>
          <form onSubmit={submit}>
            <label>Name<input required minLength={2} maxLength={80} value={name} onChange={(event) => setName(event.target.value)} /></label>
            <label>Feedback<textarea required minLength={5} maxLength={1000} rows={5} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="What could feel better?" /></label>
            {status && <small className="feedback-status" role="status">{status}</small>}
            <button className="primary" disabled={busy}>{busy ? "Sending…" : "Send feedback"}</button>
          </form>
        </section>
      </div>}
    </>
  );
}
