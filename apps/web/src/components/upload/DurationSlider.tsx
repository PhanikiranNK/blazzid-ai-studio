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
        <label className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-[#FF5722]" />
          Target Montage Duration
        </label>
        <span className="text-sm font-extrabold text-[#FF5722] font-mono bg-orange-50 px-2.5 py-0.5 rounded-lg border border-orange-200">
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
          className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#FF5722] focus:outline-none"
        />
        <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1.5 font-medium">
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
                "px-3 py-1 text-xs font-medium rounded-full border transition-all cursor-pointer shadow-xs",
                isSelected
                  ? "bg-[#FF5722] text-white border-[#FF5722] font-semibold shadow-xs"
                  : "bg-white text-slate-700 border-slate-200 hover:text-slate-900 hover:bg-slate-50"
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
