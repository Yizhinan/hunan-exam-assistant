import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import {
  LayoutDashboard,
  PenLine,
  Newspaper,
  BookOpen,
  BarChart3,
  Settings,
  LogOut,
  ChevronLeft,
  Menu,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  {
    label: "首页",
    icon: LayoutDashboard,
    href: "/",
    active: (path: string) => path === "/",
  },
  {
    label: "申论批改",
    icon: PenLine,
    href: "/essay",
    active: (path: string) => path.startsWith("/essay"),
    badge: "AI",
  },
  {
    label: "每日范文",
    icon: Newspaper,
    href: "/daily",
    active: (path: string) => path.startsWith("/daily"),
  },
  {
    label: "行测刷题",
    icon: BookOpen,
    href: "/xingce",
    active: () => false,
    disabled: true,
  },
  {
    label: "考情分析",
    icon: BarChart3,
    href: "/analysis",
    active: (path: string) => path.startsWith("/analysis"),
  },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleNav = (href: string, disabled?: boolean) => {
    if (disabled) return;
    navigate(href);
    setMobileOpen(false);
  };

  const sidebar = (
    <div
      className={`h-full flex flex-col bg-white border-r border-warm-200/80 shadow-nav transition-all duration-300 ${
        collapsed ? "w-[72px]" : "w-[240px]"
      }`}
    >
      {/* Logo */}
      <div
        className={`h-16 flex items-center border-b border-warm-100 px-5 cursor-pointer ${
          collapsed ? "justify-center" : "gap-3"
        }`}
        onClick={() => navigate("/")}
      >
        <div className="relative shrink-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-sm">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <div className="text-sm font-semibold text-warm-900 leading-tight">
              湖南公考助手
            </div>
            <div className="text-[11px] text-warm-400 leading-tight">
              Hunan Exam AI
            </div>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = item.active(location.pathname);
          return (
            <button
              key={item.href}
              onClick={() => handleNav(item.href, item.disabled)}
              disabled={item.disabled}
              className={`w-full flex items-center gap-3 rounded-xl text-sm font-medium transition-all duration-150 group relative ${
                collapsed ? "justify-center px-0 py-3" : "px-3 py-2.5"
              } ${
                item.disabled
                  ? "text-warm-300 cursor-not-allowed"
                  : isActive
                  ? "bg-brand-50 text-brand-700"
                  : "text-warm-600 hover:bg-warm-50 hover:text-warm-800"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <item.icon
                className={`h-5 w-5 shrink-0 ${
                  isActive ? "text-brand-600" : item.disabled ? "text-warm-300" : "text-warm-400"
                }`}
              />
              {!collapsed && (
                <>
                  <span className="truncate">{item.label}</span>
                  {item.badge && (
                    <span className="tag tag-green ml-auto text-[10px] px-1.5">
                      {item.badge}
                    </span>
                  )}
                  {item.disabled && (
                    <span className="text-[10px] text-warm-300 ml-auto">即将上线</span>
                  )}
                </>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className={`border-t border-warm-100 p-3 ${collapsed ? "px-2" : ""}`}>
        {/* Admin */}
        <button
          onClick={() => handleNav("/admin")}
          className={`w-full flex items-center gap-3 rounded-xl text-sm font-medium transition-all duration-150 ${
            collapsed ? "justify-center px-0 py-3" : "px-3 py-2.5"
          } text-warm-500 hover:bg-warm-50 hover:text-warm-700`}
          title={collapsed ? "管理后台" : undefined}
        >
          <Settings className="h-5 w-5 shrink-0 text-warm-400" />
          {!collapsed && <span>管理后台</span>}
        </button>

        {/* User */}
        <button
          className={`w-full flex items-center gap-3 rounded-xl transition-all duration-150 ${
            collapsed ? "justify-center px-0 py-3" : "px-3 py-2.5"
          } text-warm-500 hover:bg-warm-50`}
          title={collapsed ? user?.display_name || user?.username : undefined}
        >
          <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold shrink-0">
            {(user?.display_name || user?.username || "?")[0]}
          </div>
          {!collapsed && (
            <div className="flex-1 text-left overflow-hidden">
              <div className="text-xs font-medium text-warm-800 truncate">
                {user?.display_name || user?.username}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  logout();
                  navigate("/login");
                }}
                className="text-[11px] text-warm-400 hover:text-accent-500 flex items-center gap-1"
              >
                <LogOut className="h-3 w-3" />
                退出登录
              </button>
            </div>
          )}
        </button>

        {/* Collapse toggle (desktop) */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden md:flex w-full items-center justify-center mt-2 py-1.5 rounded-lg text-warm-300 hover:text-warm-500 hover:bg-warm-50 transition-colors"
        >
          <ChevronLeft
            className={`h-4 w-4 transition-transform ${collapsed ? "rotate-180" : ""}`}
          />
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen(true)}
        className="md:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-white shadow-card border border-warm-200 text-warm-600"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Desktop sidebar */}
      <aside className="hidden md:block h-screen sticky top-0 shrink-0 z-40">
        {sidebar}
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative z-10 h-full animate-slide-in">
            {sidebar}
          </div>
        </div>
      )}
    </>
  );
}
