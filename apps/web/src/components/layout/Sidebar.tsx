"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutGrid,
  Sparkles,
  Search,
  History,
  Film,
  Briefcase,
  Activity,
  Settings,
  ArrowLeftToLine,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  serverStatus?: {
    ready: boolean;
    db: boolean;
    redis: boolean;
  };
}

export function Sidebar({ serverStatus }: SidebarProps) {
  const pathname = usePathname();

  const primaryNav = [
    {
      label: "Studio Workspace",
      href: "/",
      icon: Sparkles,
      exact: true,
    },
    {
      label: "Find Recordings",
      href: "/#upload",
      icon: Search,
      exact: false,
    },
    {
      label: "Recent Jobs",
      href: "/#jobs",
      icon: History,
      exact: false,
    },
    {
      label: "Highlight Formats",
      href: "/#presets",
      icon: Film,
      exact: false,
    },
    {
      label: "Projects & Artifacts",
      href: "/#jobs",
      icon: Briefcase,
      exact: false,
    },
    {
      label: "Pipeline Status",
      href: "/#status",
      icon: Activity,
      exact: false,
    },
  ];

  return (
    <aside className="w-16 sm:w-20 bg-[#E8EFE9] flex flex-col items-center py-6 select-none z-30 flex-shrink-0 min-h-screen sticky top-0 justify-between">
      {/* Top Section: Brand + Navigation Dock */}
      <div className="flex flex-col items-center gap-6 w-full">
        {/* Brand Dock Button */}
        <Link
          href="/"
          className="w-10 h-10 rounded-2xl bg-white flex items-center justify-center shadow-sm border border-[#D5E0D6] text-slate-800 hover:scale-105 transition-all group"
          title="BLAZZID AI Studio"
        >
          <LayoutGrid className="w-5 h-5 text-slate-800 group-hover:text-[#FF5722] transition-colors" />
        </Link>

        {/* Navigation Items */}
        <nav className="flex flex-col items-center gap-2 w-full px-2">
          {primaryNav.map((item) => {
            const isActive = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center transition-all duration-150 group relative",
                  isActive
                    ? "bg-white text-slate-900 shadow-sm border border-[#D5E0D6]"
                    : "text-slate-600 hover:text-slate-900 hover:bg-[#DCE5DD]"
                )}
                title={item.label}
              >
                <Icon
                  className={cn(
                    "w-4 h-4 transition-colors",
                    isActive ? "text-[#FF5722]" : "text-slate-600 group-hover:text-slate-900"
                  )}
                />
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Bottom Section: Health Indicator & Settings */}
      <div className="flex flex-col items-center gap-3 w-full px-2">
        {/* Server Health Pulse */}
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center transition-all hover:bg-[#DCE5DD]"
          title={serverStatus?.ready ? "Engine: Ready & Online" : "Engine: Connecting..."}
        >
          <div className="relative flex items-center justify-center">
            <span
              className={cn(
                "w-2.5 h-2.5 rounded-full",
                serverStatus?.ready ? "bg-emerald-500" : "bg-amber-500 animate-pulse"
              )}
            />
            {serverStatus?.ready && (
              <span className="absolute w-4 h-4 rounded-full bg-emerald-400/30 animate-ping" />
            )}
          </div>
        </div>

        {/* Settings Button */}
        <button
          type="button"
          className="w-10 h-10 rounded-full flex items-center justify-center text-slate-600 hover:text-slate-900 hover:bg-[#DCE5DD] transition-colors"
          title="Studio Settings"
        >
          <Settings className="w-4 h-4" />
        </button>

        {/* Collapse Button */}
        <button
          type="button"
          className="w-10 h-10 rounded-full flex items-center justify-center text-slate-600 hover:text-slate-900 hover:bg-[#DCE5DD] transition-colors"
          title="Toggle Navigation"
        >
          <ArrowLeftToLine className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
