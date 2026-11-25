import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  BookMarked,
  Bot,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  FilePlus2,
  FileSearch2,
  FolderOpen,
  Globe,
  History,
  Layers,
  LayoutDashboard,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Sun,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { AppConfig } from "../types";

interface LayoutProps {
  config: AppConfig | null;
}

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  end?: boolean;
}

interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    id: "utama",
    label: "UTAMA",
    items: [
      { to: "/", label: "Dasbor", icon: LayoutDashboard, end: true },
      { to: "/new-check", label: "Pemeriksaan Baru", icon: FilePlus2 },
      { to: "/history", label: "Riwayat Pemeriksaan", icon: History },
    ],
  },
  {
    id: "pemeriksaan",
    label: "PEMERIKSAAN",
    items: [
      { to: "/plagiarism-checks", label: "Deteksi Plagiasi", icon: FileSearch2 },
      { to: "/ai-checks", label: "Deteksi Tulisan AI", icon: Bot },
      { to: "/combined-reports", label: "Laporan Gabungan", icon: Layers },
    ],
  },
  {
    id: "sumber",
    label: "SUMBER",
    items: [
      { to: "/documents", label: "Pustaka Dokumen", icon: FolderOpen },
      { to: "/corpus", label: "Korpus Sumber", icon: Database },
      { to: "/discovery-monitor", label: "Monitor Penemuan", icon: Globe },
      { to: "/repositories", label: "Repositori Akademik", icon: BookMarked },
    ],
  },
  {
    id: "analisis",
    label: "ANALISIS",
    items: [
      { to: "/analytics", label: "Analitik Plagiasi", icon: BarChart3, end: true },
      { to: "/analytics/ai", label: "Analitik AI", icon: Activity },
    ],
  },
  {
    id: "pengaturan",
    label: "PENGATURAN",
    items: [
      { to: "/settings", label: "Pengaturan", icon: Settings },
      { to: "/models", label: "Manajemen Model", icon: Cpu },
    ],
  },
];

export const Layout: React.FC<LayoutProps> = ({ config }) => {
  const location = useLocation();
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

  const toggleGroup = (id: string) => {
    setClosedGroups((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const iconLogo = theme === "dark" ? "/brand/logo-icon-dark.svg" : "/brand/logo-icon-light.svg";

  const isRouteActive = (item: NavItem) => {
    if (item.end) return location.pathname === item.to;
    return location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
  };

  const renderNavLink = (item: NavItem, isRailMode: boolean) => {
    const Icon = item.icon;
    const active = isRouteActive(item);
    const linkEl = (
      <NavLink
        key={`${isRailMode ? "rail-" : ""}${item.to}`}
        to={item.to}
        end={item.end}
        onClick={() => setMobileOpen(false)}
        aria-label={isRailMode ? item.label : undefined}
        className={cn(
          "flex items-center rounded-lg text-sm font-medium transition-colors cursor-pointer",
          isRailMode ? "mx-auto size-9 justify-center p-0" : "gap-3 px-3 py-2",
          active
            ? "bg-primary text-primary-foreground shadow-sm"
            : "text-foreground/80 hover:bg-accent hover:text-foreground"
        )}
      >
        <Icon className="size-4 shrink-0" aria-hidden="true" />
        {!isRailMode && <span className="truncate">{item.label}</span>}
      </NavLink>
    );

    if (isRailMode) {
      return (
        <Tooltip key={`tip-${item.to}`}>
          <TooltipTrigger asChild>{linkEl}</TooltipTrigger>
          <TooltipContent side="right" className="font-medium">
            {item.label}
          </TooltipContent>
        </Tooltip>
      );
    }
    return linkEl;
  };

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex min-h-screen w-full bg-background text-foreground">
        {mobileOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[1px] md:hidden"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
        )}

        <aside
          aria-label="Navigasi utama"
          className={cn(
            "flex-col border-r border-border bg-card transition-all duration-200",
            collapsed ? "md:w-[68px]" : "md:w-[260px]",
            mobileOpen
              ? "fixed inset-y-0 left-0 z-50 flex w-[272px] shadow-lg"
              : "hidden md:sticky md:top-0 md:z-30 md:flex md:h-screen"
          )}
        >
          {/* Brand Header using Official NaskahGuard Brand Kit SVGs */}
          <div
            className={cn(
              "flex h-16 shrink-0 items-center border-b border-border",
              collapsed ? "justify-center px-2 md:flex-col md:gap-1 md:py-2" : "justify-between gap-2 px-4"
            )}
          >
            <div className={cn("flex items-center gap-2.5 min-w-0", collapsed && "md:justify-center")}>
              <img src={iconLogo} alt={appName} className="size-8 shrink-0 object-contain" />
              <div className={cn("flex flex-col min-w-0", collapsed && "md:hidden")}>
                <span className="truncate font-serif text-lg font-semibold leading-tight tracking-tight text-foreground">
                  {appName}
                </span>
                <span className="truncate text-[11px] text-muted-foreground">Integritas Akademik</span>
              </div>
            </div>

            {!collapsed && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="hidden md:inline-flex size-8 shrink-0 text-foreground/75 hover:text-foreground"
                onClick={() => setCollapsed(true)}
                aria-label="Ciutkan bilah samping"
                title="Ciutkan bilah samping"
              >
                <PanelLeftClose className="size-4" aria-hidden="true" />
              </Button>
            )}

            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="md:hidden size-8 shrink-0 text-foreground"
              onClick={() => setMobileOpen(false)}
              aria-label="Tutup menu navigasi"
            >
              <X className="size-4" aria-hidden="true" />
            </Button>
          </div>

          {/* Expand trigger neatly placed in rail mode */}
          {collapsed && (
            <div className="hidden md:flex justify-center border-b border-border py-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-8 text-foreground/80 hover:text-foreground"
                    onClick={() => setCollapsed(false)}
                    aria-label="Perluas bilah samping"
                  >
                    <PanelLeftOpen className="size-4" aria-hidden="true" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">Perluas menu</TooltipContent>
              </Tooltip>
            </div>
          )}

          {/* Navigation Groups */}
          <nav
            className={cn(
              "flex-1 overflow-y-auto",
              collapsed ? "no-scrollbar px-1.5 py-2.5" : "px-3 py-4"
            )}
          >
            <div className={cn("flex flex-col", collapsed ? "gap-1.5" : "gap-4")}>
              {NAV_GROUPS.map((group, gIdx) => {
                const isOpen = !closedGroups[group.id];
                if (collapsed) {
                  return (
                    <div key={group.id} className="hidden md:flex flex-col items-center gap-1">
                      {gIdx > 0 && <Separator className="my-1 w-7" />}
                      {group.items.map((item) => renderNavLink(item, true))}
                    </div>
                  );
                }
                return (
                  <Collapsible key={group.id} open={isOpen} onOpenChange={() => toggleGroup(group.id)}>
                    <CollapsibleTrigger className="flex w-full items-center justify-between px-2.5 py-1 text-[11px] font-semibold tracking-[0.08em] text-muted-foreground hover:text-foreground cursor-pointer">
                      <span>{group.label}</span>
                      {isOpen ? (
                        <ChevronDown className="size-3.5" aria-hidden="true" />
                      ) : (
                        <ChevronRight className="size-3.5" aria-hidden="true" />
                      )}
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-1 flex flex-col gap-0.5">
                      {group.items.map((item) => renderNavLink(item, false))}
                    </CollapsibleContent>
                  </Collapsible>
                );
              })}

              {/* Mobile drawer always renders full labels even if desktop rail was collapsed */}
              {collapsed &&
                NAV_GROUPS.map((group) => (
                  <div key={`mob-${group.id}`} className="flex flex-col gap-1 md:hidden">
                    <span className="px-2.5 py-1 text-[11px] font-semibold tracking-[0.08em] text-muted-foreground">
                      {group.label}
                    </span>
                    {group.items.map((item) => renderNavLink(item, false))}
                  </div>
                ))}
            </div>
          </nav>

          {/* Footer Theme Switcher & Brand Meta */}
          <div className={cn("shrink-0 border-t border-border flex flex-col gap-2", collapsed ? "items-center p-2" : "p-3")}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  size={collapsed ? "icon" : "sm"}
                  className={cn(collapsed ? "size-9" : "w-full justify-start")}
                  onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
                  aria-label="Ubah tema tampilan"
                >
                  {theme === "light" ? (
                    <Moon className="size-4" data-icon={collapsed ? undefined : "inline-start"} aria-hidden="true" />
                  ) : (
                    <Sun className="size-4" data-icon={collapsed ? undefined : "inline-start"} aria-hidden="true" />
                  )}
                  {!collapsed && <span>{theme === "light" ? "Mode Gelap" : "Mode Terang"}</span>}
                </Button>
              </TooltipTrigger>
              {collapsed && (
                <TooltipContent side="right">
                  {theme === "light" ? "Aktifkan Mode Gelap" : "Aktifkan Mode Terang"}
                </TooltipContent>
              )}
            </Tooltip>
            {!collapsed && (
              <p className="px-1 text-[11px] leading-snug text-muted-foreground">
                Lokal &amp; Terkendali Pengguna · v{config?.version || "1.0"}
              </p>
            )}
          </div>
        </aside>

        {/* Main Workspace Column */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Mobile Only Top Header */}
          <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-card px-4 md:hidden">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setMobileOpen(true)}
              aria-label="Buka menu navigasi"
            >
              <Menu className="size-4" data-icon="inline-start" aria-hidden="true" />
              <span>Menu</span>
            </Button>
            <div className="flex items-center gap-2">
              <img src={iconLogo} alt={appName} className="size-6 object-contain" />
              <span className="font-serif text-base font-semibold text-foreground">{appName}</span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
              aria-label="Ubah tema"
            >
              {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
            </Button>
          </header>

          <main className="mx-auto w-full max-w-[1360px] flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
            <Outlet />
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
};
