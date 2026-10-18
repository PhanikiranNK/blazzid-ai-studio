"use client";

import React from "react";
import { Sparkles, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface TopBarProps {
  onNewEdit?: () => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function TopBar({ onNewEdit, onRefresh, isRefreshing }: TopBarProps) {
  return (
    <header className="h-16 border-b border-[#D8E2D9] bg-[#E8EFE9]/80 backdrop-blur-md px-6 sm:px-8 flex items-center justify-between sticky top-0 z-20 select-none">
      <div className="flex items-center gap-3">
        <h1 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
          Gameplay Highlight Studio
        </h1>
        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-white border border-[#D5DFD5] text-slate-700 shadow-2xs">
          Brawl Stars Edition
        </span>
      </div>

      <div className="flex items-center gap-3">
        {onRefresh && (
          <Button
            variant="secondary"
            size="sm"
            onClick={onRefresh}
            isLoading={isRefreshing}
            title="Refresh active jobs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        )}

        {onNewEdit && (
          <Button variant="primary" size="sm" onClick={onNewEdit}>
            <Sparkles className="w-3.5 h-3.5 fill-current" />
            <span>New Highlight</span>
          </Button>
        )}
      </div>
    </header>
  );
}
