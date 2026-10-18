"use client";

import React from "react";
import { Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface DurationSliderProps {
  duration: number;
  onChange: (val: number) => void;
  min?: number;
  max?: number;
}

export function DurationSlider({
  duration,
  onChange,
  min = 5.0,
  max = 300.0,
}: DurationSliderProps) {
  const presets = [
    { label: "15s Shorts", value: 15 },
    { label: "30s Standard", value: 30 },
    { label: "60s Full Reel", value: 60 },
    { label: "90s Montage", value: 90 },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-amber-400" />
          Target Montage Duration
        </label>
        <span className="text-sm font-extrabold text-amber-400 font-mono bg-amber-500/10 px-2.5 py-0.5 rounded-lg border border-amber-500/20">
          {Math.round(duration)} seconds
        </span>
      </div>

      {/* Range Input */}
      <div className="relative pt-1">
        <input
          type="range"
          min={min}
          max={max}
          step={5}
          value={duration}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-[#1b2033] rounded-lg appearance-none cursor-pointer accent-amber-500 focus:outline-none"
        />
        <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-1.5">
          <span>{min}s (Min)</span>
          <span>60s</span>
          <span>180s</span>
          <span>{max}s (Max)</span>
        </div>
      </div>

      {/* Preset Pills */}
      <div className="flex flex-wrap gap-2 pt-1">
        {presets.map((preset) => {
          const isSelected = Math.round(duration) === preset.value;
          return (
            <button
              key={preset.value}
              type="button"
              onClick={() => onChange(preset.value)}
              className={cn(
                "px-2.5 py-1 text-xs font-medium rounded-lg border transition-all cursor-pointer",
                isSelected
                  ? "bg-amber-500/20 text-amber-400 border-amber-500/40 font-semibold"
                  : "bg-[#111422] text-slate-400 border-[#1e2436] hover:text-slate-200 hover:border-[#2b334d]"
              )}
            >
              {preset.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
