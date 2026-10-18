"use client";

import React from "react";
import { Crosshair, Sparkles, Music, Volume2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ViralEffectsState {
  autoZoom: boolean;
  memeOverlays: boolean;
  soundtrack: "phonk" | "cyber" | "trap" | "none";
}

interface ViralEffectsSelectorProps {
  effects: ViralEffectsState;
  onChange: (effects: ViralEffectsState) => void;
}

export function ViralEffectsSelector({
  effects,
  onChange,
}: ViralEffectsSelectorProps) {
  const musicOptions: {
    id: "phonk" | "cyber" | "trap" | "none";
    label: string;
    sub: string;
  }[] = [
    {
      id: "phonk",
      label: "Phonk Drift",
      sub: "135 BPM • Heavy 808 & Cowbell",
    },
    {
      id: "cyber",
      label: "Cyber Arcade",
      sub: "140 BPM • Synthwave Energy",
    },
    {
      id: "trap",
      label: "Trap Montage",
      sub: "130 BPM • Brass Stabs & Hi-Hats",
    },
    {
      id: "none",
      label: "Original Audio",
      sub: "Game SFX Only (No Music)",
    },
  ];

  return (
    <div className="space-y-4 pt-1">
      <div className="flex items-center justify-between">
        <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
          Viral Edit Enhancements & FX
        </label>
        <span className="text-[11px] font-semibold text-[#FF5722] bg-orange-50 px-2.5 py-0.5 rounded-full border border-orange-200">
          Smart AI Overlays
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* 1. Dynamic Auto-Zoom Toggle */}
        <button
          type="button"
          onClick={() => onChange({ ...effects, autoZoom: !effects.autoZoom })}
          className={cn(
            "p-4 rounded-2xl border text-left transition-all duration-150 cursor-pointer flex items-start gap-3.5 group shadow-xs",
            effects.autoZoom
              ? "bg-white border-[#FF5722] ring-1 ring-[#FF5722]/40"
              : "bg-[#F9FAF9] border-[#E3E8E3] hover:border-slate-300"
          )}
        >
          <div
            className={cn(
              "w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors shadow-2xs",
              effects.autoZoom
                ? "bg-orange-50 text-[#FF5722]"
                : "bg-white text-slate-500 border border-slate-200"
            )}
          >
            <Crosshair className="w-4 h-4" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs sm:text-sm text-slate-900">
                Action Cam Auto-Zoom
              </span>
              <span
                className={cn(
                  "text-[10px] font-bold px-2 py-0.5 rounded-full",
                  effects.autoZoom
                    ? "bg-[#FF5722] text-white"
                    : "bg-slate-200 text-slate-600"
                )}
              >
                {effects.autoZoom ? "ACTIVE" : "OFF"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
              Dynamically zooms in 1.25x on climaxes and eliminations to highlight critical combat plays.
            </p>
          </div>
        </button>

        {/* 2. Meme Badges & Reaction Overlays Toggle */}
        <button
          type="button"
          onClick={() =>
            onChange({ ...effects, memeOverlays: !effects.memeOverlays })
          }
          className={cn(
            "p-4 rounded-2xl border text-left transition-all duration-150 cursor-pointer flex items-start gap-3.5 group shadow-xs",
            effects.memeOverlays
              ? "bg-white border-[#FF5722] ring-1 ring-[#FF5722]/40"
              : "bg-[#F9FAF9] border-[#E3E8E3] hover:border-slate-300"
          )}
        >
          <div
            className={cn(
              "w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors shadow-2xs",
              effects.memeOverlays
                ? "bg-orange-50 text-[#FF5722]"
                : "bg-white text-slate-500 border border-slate-200"
            )}
          >
            <Sparkles className="w-4 h-4" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs sm:text-sm text-slate-900">
                Meme & Reaction Badges
              </span>
              <span
                className={cn(
                  "text-[10px] font-bold px-2 py-0.5 rounded-full",
                  effects.memeOverlays
                    ? "bg-[#FF5722] text-white"
                    : "bg-slate-200 text-slate-600"
                )}
              >
                {effects.memeOverlays ? "ACTIVE" : "OFF"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
              Pops K.O., 200 IQ, and Victory stickers at peak elimination moments with arcade flair.
            </p>
          </div>
        </button>
      </div>

      {/* 3. Trending Soundtrack Selector */}
      <div className="p-4 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
            <Music className="w-3.5 h-3.5 text-[#FF5722]" />
            Trending Montage Soundtrack (BGM)
          </label>
          <span className="text-[11px] text-slate-500 font-medium flex items-center gap-1">
            <Volume2 className="w-3 h-3 text-slate-400" />
            Auto-ducked under game SFX
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {musicOptions.map((opt) => {
            const isSelected = effects.soundtrack === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => onChange({ ...effects, soundtrack: opt.id })}
                className={cn(
                  "p-3 rounded-xl border text-left transition-all cursor-pointer shadow-2xs flex flex-col justify-between group",
                  isSelected
                    ? "bg-white border-[#FF5722] ring-1 ring-[#FF5722]/30 shadow-xs"
                    : "bg-white/80 border-[#E2E8E2] hover:border-slate-300 hover:bg-white"
                )}
              >
                <span
                  className={cn(
                    "font-bold text-xs block truncate",
                    isSelected ? "text-[#FF5722]" : "text-slate-800"
                  )}
                >
                  {opt.label}
                </span>
                <span className="text-[10px] text-slate-500 block truncate mt-0.5">
                  {opt.sub}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
