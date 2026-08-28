import React from "react";
export default function Sidebar({
  user,
  nav,
  view,
  setView,
  apiUrl,
  onLogout,
}) {
  return (
    <aside>
      <div className="brand">
        INTAIN <span>VERIFY</span>
      </div>
      <p className="role">{user.role.replace("_", " ")}</p>
      {nav.map((item) => (
        <button
          key={item}
          className={view === item ? "nav active" : "nav"}
          onClick={() => setView(item)}
        >
          {item}
        </button>
      ))}
      <button
        className="nav"
        onClick={() => window.open(`${apiUrl}/docs`, "_blank")}
      >
        API Docs
      </button>
      <button className="logout" onClick={onLogout}>
        Sign out
      </button>
    </aside>
  );
}
