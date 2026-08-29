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
    <aside className="sidebar" aria-label="Application navigation">
      <div className="sidebar-top">
        <div className="brand">
          INTAIN <span>VERIFY</span>
        </div>
        <p className="role">{user.role.replace("_", " ")}</p>
      </div>
      <nav className="sidebar-nav">
        {nav.map((item) => (
          <button
            key={item}
            className={view === item ? "nav active" : "nav"}
            onClick={() => setView(item)}
          >
            {item}
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <button
          className="nav"
          onClick={() => window.open(`${apiUrl}/docs`, "_blank")}
        >
          API Docs
        </button>
        <button className="logout" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
