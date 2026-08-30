import React from "react";

export default function SpeedLoader({ message = "Closing secure session…" }) {
  return (
    <div className="speed-loader-overlay" role="status" aria-live="assertive">
      <div className="speed-lines" aria-hidden="true"><i /><i /><i /><i /></div>
      <div className="speed-loader-art" aria-hidden="true">
        <span className="speed-trails"><i /><i /><i /><i /></span>
        <div className="speed-base"><span /></div>
        <div className="speed-face" />
      </div>
      <p>{message}</p>
    </div>
  );
}
