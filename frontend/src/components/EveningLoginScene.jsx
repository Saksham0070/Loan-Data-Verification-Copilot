import React, { useEffect, useState } from "react";

function getTimePhase(date = new Date()) {
  const hour = date.getHours();
  if (hour >= 5 && hour < 10) return "sunrise";
  if (hour >= 10 && hour < 17) return "day";
  if (hour >= 17 && hour < 20) return "sunset";
  return "night";
}

export default function EveningLoginScene() {
  const [phase, setPhase] = useState(() => getTimePhase());

  useEffect(() => {
    const timer = window.setInterval(() => setPhase(getTimePhase()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className={`login-scene scene-${phase}`} aria-hidden="true">
      <div className="scene-stars">{Array.from({ length: 16 }, (_, index) => <i key={index} />)}</div>
      <div className="scene-celestial"><span /></div>
      <div className="scene-cloud scene-cloud-one" />
      <div className="scene-cloud scene-cloud-two" />
      <div className="scene-horizon" />
      <div className="scene-hill scene-hill-back" />
      <div className="scene-hill scene-hill-front" />
      <div className="scene-windmill">
        <div className="windmill-cap" />
        <div className="windmill-tower"><i /></div>
        <div className="windmill-blades">
          {Array.from({ length: 4 }, (_, index) => <span key={index} style={{ "--blade-index": index }} />)}
          <b />
        </div>
      </div>
      <div className="scene-grass" />
    </div>
  );
}
