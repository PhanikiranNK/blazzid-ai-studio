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
      <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
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
                "relative text-left p-4 sm:p-5 rounded-2xl border transition-all duration-150 cursor-pointer flex flex-col justify-between group",
                isSelected
                  ? "bg-white border-[#FF5722] shadow-sm shadow-orange-500/10 ring-1 ring-[#FF5722]"
                  : "bg-[#F9FAF9] border-[#E3E8E3] hover:border-[#FF5722]/50 hover:bg-orange-50/10"
              )}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div
                    className={cn(
                      "w-8 h-8 rounded-xl flex items-center justify-center transition-colors shadow-xs",
                      isSelected
                        ? "bg-orange-50 text-[#FF5722]"
                        : "bg-white text-slate-700 border border-slate-200/60 group-hover:text-[#FF5722]"
                    )}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  {isSelected && (
                    <div className="w-5 h-5 rounded-full bg-[#FF5722] text-white flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                  )}
                </div>
                <div className="font-bold text-sm text-slate-900 mb-1">
                  {p.title}
                </div>
                <div className="text-xs text-slate-600 leading-relaxed mb-3">
                  {p.description}
                </div>
              </div>

              <div
                className={cn(
                  "text-[10px] font-mono px-2 py-0.5 rounded-full border inline-block w-fit font-medium",
                  isSelected
                    ? "bg-orange-50 text-[#FF5722] border-orange-200"
                    : "bg-white text-slate-600 border-slate-200"
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
