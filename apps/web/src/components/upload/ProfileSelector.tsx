"use client";

import React from "react";
import { AssemblyProfile, AspectRatio } from "@/types/api";
import { Smartphone, Monitor, Wand2, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProfileSelectorProps {
  selectedProfile: AssemblyProfile;
  selectedAspectRatio: AspectRatio;
  onSelect: (profile: AssemblyProfile, ratio: AspectRatio) => void;
}

export function ProfileSelector({
  selectedProfile,
  onSelect,
}: ProfileSelectorProps) {
  const profiles: {
    id: AssemblyProfile;
    ratio: AspectRatio;
    title: string;
    description: string;
    badge: string;
    icon: React.ComponentType<{ className?: string }>;
  }[] = [
    {
      id: "youtube_shorts",
      ratio: "9:16",
      title: "Vertical Shorts",
      description: "Optimized for YouTube Shorts, Reels, and TikTok",
      badge: "9:16 Vertical (1080x1920)",
      icon: Smartphone,
    },
    {
      id: "landscape_16_9",
      ratio: "16:9",
      title: "Widescreen HD",
      description: "Classic cinematic format for YouTube & Twitch",
      badge: "16:9 Landscape (1920x1080)",
      icon: Monitor,
    },
    {
      id: "dynamic",
      ratio: "9:16",
      title: "Smart Adaptive",
      description: "Dynamically sizes based on combat action density",
      badge: "AI Optimal Assembly",
      icon: Wand2,
    },
  ];

  return (
    <div className="space-y-3">
      <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
        Assembly Format & Profile
      </label>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {profiles.map((p) => {
          const isSelected = selectedProfile === p.id;
          const Icon = p.icon;

          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelect(p.id, p.ratio)}
              className={cn(
                "relative text-left p-4 rounded-xl border transition-all duration-150 cursor-pointer flex flex-col justify-between group",
                isSelected
                  ? "bg-[#181d2e] border-amber-500/80 shadow-lg shadow-amber-500/10 ring-1 ring-amber-500/40"
                  : "bg-[#111420] border-[#1d2336] hover:border-[#2b334d] hover:bg-[#141826]"
              )}
            >
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <div
                    className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center transition-colors",
                      isSelected
                        ? "bg-amber-500/20 text-amber-400"
                        : "bg-slate-800/60 text-slate-400 group-hover:text-slate-300"
                    )}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  {isSelected && (
                    <div className="w-5 h-5 rounded-full bg-amber-500 text-slate-950 flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                  )}
                </div>
                <div className="font-bold text-sm text-white mb-1">
                  {p.title}
                </div>
                <div className="text-xs text-slate-400 leading-relaxed mb-3">
                  {p.description}
                </div>
              </div>

              <div
                className={cn(
                  "text-[10px] font-mono px-2 py-0.5 rounded border inline-block w-fit",
                  isSelected
                    ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                    : "bg-slate-800/40 text-slate-400 border-slate-700/50"
                )}
              >
                {p.badge}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
