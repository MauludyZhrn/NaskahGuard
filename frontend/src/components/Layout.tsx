import React, { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  FilePlus2,
  History,
  FolderOpen,
  Database,
  Globe,
  BookMarked,
  FileBarChart2,
  BarChart3,
  Settings,
  Sun,
  Moon,
  Menu,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { AppConfig } from "../types";

interface LayoutProps {
  config: AppConfig | null;
}

interface NavGroup {
  id: string;
  label: string;
  items: Array<{ to: string; label: string; icon: React.ComponentType<{ size?: number | string }>; end?: boolean }>;
}

const NAV_GROUPS: NavGroup[] = [
  {
    id: "utama",
    label: "Utama",
    items: [
      { to: "/", label: "Dasbor", icon: LayoutDashboard, end: true },
      { to: "/new-check", label: "Pemeriksaan Baru", icon: FilePlus2 },
      { to: "/history", label: "Riwayat Pemeriksaan", icon: History },
    ],
  },
  {
    id: "sumber",
    label: "Sumber",
    items: [
      { to: "/documents", label: "Pustaka Dokumen", icon: FolderOpen },
      { to: "/corpus", label: "Korpus Sumber", icon: Database },
      { to: "/discovery-monitor", label: "Monitor Penemuan", icon: Globe },
      { to: "/repositories", label: "Repositori Akademik", icon: BookMarked },
    ],
  },
  {
    id: "analisis",
    label: "Analisis",
    items: [
      { to: "/reports", label: "Laporan Kemiripan", icon: FileBarChart2 },
      { to: "/analytics", label: "Analitik", icon: BarChart3 },
    ],
  },
  {
    id: "pengaturan",
    label: "Pengaturan",
    items: [{ to: "/settings", label: "Pengaturan", icon: Settings }],
  },
];

export const Layout: React.FC<LayoutProps> = ({ config }) => {
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    localStorage.getItem("ng_theme") === "dark" ? "dark" : "light"
  );
  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem("ng_sidebar_collapsed") === "true"
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [closedGroups, setClosedGroups] = useState<Record<string, boolean>>({});

  const appName = config?.app_name || import.meta.env.VITE_APP_NAME || "NaskahGuard";

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("ng_theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("ng_sidebar_collapsed", String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    document.title = `${appName} — Pemeriksa Kemiripan Dokumen Akademik`;
  }, [appName]);

  const toggleGroup = (id: string) => {
    setClosedGroups((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <TooltipProvider delayDuration={120}>
      <div className="app-shell">
        <div
          className={`drawer-backdrop ${mobileOpen ? "open" : ""}`}
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />

        <aside
          className={`sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "open" : ""}`}
          aria-label="Navigasi utama"
          data-collapsed={collapsed ? "true" : "false"}
        >
          <div className="brand-row">
            <div className="brand-mark">
              <span className="brand-icon" aria-hidden="true">
                NG
              </span>
              {!collapsed && (
                <div style={{ minWidth: 0 }}>
                  <h1 className="brand-title">{appName}</h1>
                  <div className="brand-sub">Audit Integritas Akademik</div>
                </div>
              )}
            </div>

            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="btn btn-icon desktop-collapse-btn"
                  onClick={() => setCollapsed((c) => !c)}
                  aria-label={collapsed ? "Perluas sidebar" : "Ciutkan sidebar"}
                  aria-expanded={!collapsed}
                >
                  {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {collapsed ? "Perluas sidebar" : "Ciutkan sidebar"}
              </TooltipContent>
            </Tooltip>

            <button
              type="button"
              className="btn btn-icon mobile-toggle"
              aria-label="Tutup menu navigasi"
              onClick={() => setMobileOpen(false)}
            >
              <X size={16} />
            </button>
          </div>

          <nav className="nav-scroll">
            {NAV_GROUPS.map((group) => {
              const isOpen = !(Boolean(closedGroups[group.id]) && !collapsed);
              return (
                <Collapsible key={group.id} open={isOpen} onOpenChange={() => toggleGroup(group.id)}>
                  {!collapsed && (
                    <CollapsibleTrigger asChild>
                      <button type="button" className="nav-group-header" aria-expanded={isOpen}>
                        <span>{group.label}</span>
                        {!isOpen ? <ChevronRight size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
                      </button>
                    </CollapsibleTrigger>
                  )}

                  <CollapsibleContent forceMount={collapsed ? true : undefined}>
                    {isOpen && (
                      <div className="nav-list">
                        {group.items.map((item) => {
                          const Icon = item.icon;
                          const linkNode = (
                            <NavLink
                              key={item.to}
                              to={item.to}
                              end={item.end}
                              onClick={() => setMobileOpen(false)}
                              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                              aria-label={item.label}
                            >
                              <Icon size={18} />
                              {!collapsed && <span>{item.label}</span>}
                            </NavLink>
                          );
                          if (!collapsed) return linkNode;
                          return (
                            <Tooltip key={item.to}>
                              <TooltipTrigger asChild>{linkNode}</TooltipTrigger>
                              <TooltipContent side="right">{item.label}</TooltipContent>
                            </Tooltip>
                          );
                        })}
                      </div>
                    )}
                  </CollapsibleContent>
                </Collapsible>
              );
            })}
          </nav>

          {!collapsed && (
            <div className="sidebar-footer">
              <div>Mode: Local-First (SQLite)</div>
              {config && <div>PDF: {config.pdf_backend} · Maks {config.max_upload_mb} MB</div>}
            </div>
          )}
        </aside>

        <div className="main-area">
          <header className="topbar">
            <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              <button
                type="button"
                className="btn btn-icon mobile-toggle"
                aria-label="Buka menu navigasi"
                onClick={() => setMobileOpen(true)}
              >
                <Menu size={17} />
              </button>
              <span
                style={{
                  fontSize: 13.5,
                  color: "var(--text-secondary)",
                  fontWeight: 500,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                Platform Pemeriksaan Kemiripan &amp; Intelijen Sumber Akademik
              </span>
            </div>

            <button
              type="button"
              className="btn"
              onClick={() => setTheme((prev) => (prev === "light" ? "dark" : "light"))}
              aria-label={theme === "light" ? "Aktifkan mode gelap" : "Aktifkan mode terang"}
            >
              {theme === "light" ? <Moon size={15} /> : <Sun size={15} />}
              <span>{theme === "light" ? "Mode Gelap" : "Mode Terang"}</span>
            </button>
          </header>

          <main className="page-content">
            <Outlet />
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
};
