"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Film,
  Sparkles,
  Layers,
  History,
  Activity,
  Code2,
  Cpu,
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

  const navItems = [
    {
      label: "Studio Workspace",
      href: "/",
      icon: Sparkles,
      exact: true,
    },
    {
      label: "Recent Jobs",
      href: "/#jobs",
      icon: History,
      exact: false,
    },
  ];

  return (
    <aside className="w-64 bg-[#0e111a] border-r border-[#1a1f30] flex flex-col h-screen sticky top-0 select-none z-30">
      {/* Brand Header */}
      <div className="h-16 px-6 flex items-center gap-3 border-b border-[#1a1f30]">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20 text-slate-950">
          <Film className="w-5 h-5 fill-current" />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <span className="font-extrabold text-base tracking-tight text-white">
              BLAZZID
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
              AI
            </span>
          </div>
          <p className="text-[11px] text-slate-400 font-medium">
            Gaming Video Intelligence
          </p>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 px-3 py-6 space-y-1">
        <div className="px-3 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
          Creative Tools
        </div>
        {navItems.map((item) => {
          const isActive = item.exact
            ? pathname === item.href
            : pathname.startsWith(item.href);
          const Icon = item.icon;

          return (
            <Link
              key={item.label}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all group",
                isActive
                  ? "bg-[#181d2e] text-white shadow-sm border border-[#272f48]"
                  : "text-slate-400 hover:text-slate-200 hover:bg-[#131724]"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4 transition-colors",
                  isActive
                    ? "text-amber-400"
                    : "text-slate-500 group-hover:text-slate-300"
                )}
              />
              <span>{item.label}</span>
            </Link>
          );
        })}

        {/* Pipeline Specification Summary Card */}
        <div className="pt-6">
          <div className="px-3 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Pipeline Architecture
          </div>
          <div className="p-3.5 rounded-xl bg-[#131622] border border-[#1e2335] text-xs space-y-2.5">
            <div className="flex items-center justify-between text-slate-300 font-semibold">
              <span className="flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                Pipeline Stages
              </span>
              <span className="text-[10px] text-slate-400 font-mono">v5.1</span>
            </div>
            <div className="space-y-1 text-[11px] text-slate-400">
              <div className="flex items-center justify-between">
                <span>1. Media Ingestion</span>
                <span className="text-emerald-400 font-mono">CV2/FFmpeg</span>
              </div>
              <div className="flex items-center justify-between">
                <span>2. Event Detection</span>
                <span className="text-amber-400 font-mono">A/V Bursts</span>
              </div>
              <div className="flex items-center justify-between">
                <span>3. Budgeted Assembly</span>
                <span className="text-indigo-400 font-mono">DP Knapsack</span>
              </div>
              <div className="flex items-center justify-between">
                <span>4. FFmpeg Montage</span>
                <span className="text-cyan-400 font-mono">1080x1920</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Backend Health & Status */}
      <div className="p-4 border-t border-[#1a1f30] bg-[#0b0d14]/70 space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1.5 text-slate-400 font-medium">
            <Activity className="w-3.5 h-3.5 text-amber-400" />
            Backend Engine
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full border",
              serverStatus?.ready
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
            )}
          >
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full animate-pulse",
                serverStatus?.ready ? "bg-emerald-400" : "bg-amber-400"
              )}
            />
            {serverStatus?.ready ? "ONLINE" : "INITIALIZING"}
          </span>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
          <span className="flex items-center gap-1">
            <Cpu className="w-3 h-3 text-slate-500" />
            PostgreSQL + Redis
          </span>
          <span className="font-mono text-slate-400">Streams v7</span>
        </div>

        <a
          href="https://github.com/PhanikiranNK/blazzid-ai-studio"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 w-full py-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>GitHub Monorepo</span>
        </a>
      </div>
    </aside>
  );
}
