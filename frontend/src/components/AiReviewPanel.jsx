import React from "react";

/** Visible human-in-the-loop AI panel. It never makes a decision by itself. */
export default function AiReviewPanel({ enabled, ai, busy, onRequest }) {
  if (!enabled)
    return (
      <div className="ai ai-disabled">
        <span>AI REVIEW ASSISTANT</span>
        <p>
          Sign in as a Reviewer to request a Groq explanation and
          recommendation.
        </p>
      </div>
    );
  if (!ai)
    return (
      <div className="ai ai-empty">
        <span>GROQ AI REVIEW ASSISTANT</span>
        <h3>Explain this exception</h3>
        <p>
          Groq will inspect the selected loan and validation failure, then
          provide a recommendation for a human reviewer. It cannot update or
          approve the loan.
        </p>
        <button className="primary" disabled={busy} onClick={onRequest}>
          {busy ? "Generating review…" : "Ask Groq AI"}
        </button>
      </div>
    );
  return (
    <div className="ai">
      <span>GROQ RECOMMENDATION · {ai.model}</span>
      <h3>{ai.response?.severity || "Review"} assessment</h3>
      <p>{ai.response?.explanation}</p>
      <div className="ai-suggestion">
        <b>Suggested correction</b>
        <strong>
          {ai.response?.suggested_field}: {String(ai.response?.suggested_value)}
        </strong>
      </div>
      <p className="reasoning">{ai.response?.reasoning}</p>
      <small>
        Confidence: {ai.response?.confidence} · Recommendation only; reviewer
        approval is required.
      </small>
    </div>
  );
}
