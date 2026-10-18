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
    <header className="h-16 border-b border-[#1a1f30] bg-[#0c0e17]/80 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-20 select-none">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
          Gameplay Highlight Studio
        </h1>
        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-[#181d2c] border border-[#262e45] text-slate-300">
          Brawl Stars Edition
        </span>
      </div>

      <div className="flex items-center gap-3">
        {onRefresh && (
          <Button
            variant="ghost"
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
