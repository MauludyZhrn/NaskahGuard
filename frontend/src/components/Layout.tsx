import React, { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  FilePlus2,
  History,
  FolderOpen,
  Database,
  FileBarChart2,
  Settings,
  Sun,
  Moon,
  Menu,
  X,
} from "lucide-react";
import { AppConfig } from "../types";

interface LayoutProps {
  config: AppConfig | null;
}

const NAV_ITEMS = [
  { to: "/", label: "Dasbor", icon: LayoutDashboard, end: true },
  { to: "/new-check", label: "Pemeriksaan Baru", icon: FilePlus2 },
  { to: "/history", label: "Riwayat Pemeriksaan", icon: History },
  { to: "/documents", label: "Pustaka Dokumen", icon: FolderOpen },
  { to: "/corpus", label: "Korpus Sumber", icon: Database },
  { to: "/reports", label: "Laporan Kemiripan", icon: FileBarChart2 },
  { to: "/settings", label: "Pengaturan", icon: Settings },
];

export const Layout: React.FC<LayoutProps> = ({ config }) => {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("ng_theme");
    return saved === "dark" ? "dark" : "light";
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  const appName = config?.app_name || import.meta.env.VITE_APP_NAME || "NaskahGuard";

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("ng_theme", theme);
  }, [theme]);

  useEffect(() => {
    document.title = `${appName} — Pemeriksa Kemiripan Dokumen Akademik`;
  }, [appName]);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`} aria-label="Navigasi utama">
        <div className="brand" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1 className="brand-title">{appName}</h1>
            <div className="brand-sub">Deteksi Kemiripan Akademik</div>
          </div>
          <button
            type="button"
            className="btn mobile-toggle"
            aria-label="Tutup menu"
            onClick={() => setMobileOpen(false)}
            style={{ padding: "4px 8px" }}
          >
            <X size={16} />
          </button>
        </div>

        <nav className="nav-list">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
              >
                <Icon size={17} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div style={{ fontSize: 12, color: "var(--text-muted)", padding: "12px 10px 0", borderTop: "1px solid var(--border)" }}>
          <div>Mode: Local-First</div>
          {config && <div>PDF: {config.pdf_backend} · Maks {config.max_upload_mb} MB</div>}
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              type="button"
              className="btn mobile-toggle"
              aria-label="Buka menu navigasi"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={17} />
            </button>
            <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              Sistem Audit Kemiripan Naskah Terbuka &amp; Terukur
            </span>
          </div>

          <button
            type="button"
            className="btn"
            onClick={() => setTheme((prev) => (prev === "light" ? "dark" : "light"))}
            aria-label={theme === "light" ? "Aktifkan mode gelap" : "Aktifkan mode terang"}
          >
            {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            <span>{theme === "light" ? "Mode Gelap" : "Mode Terang"}</span>
          </button>
        </header>

        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
