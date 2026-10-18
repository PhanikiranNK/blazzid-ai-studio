"use client";

import React from "react";
import { Film, Zap, Clock, Cpu } from "lucide-react";

export function StudioBentoCards() {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-bold text-slate-800">Pipeline Highlights</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Card 1 */}
        <div className="p-5 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] flex flex-col justify-between">
          <div>
            <div className="w-9 h-9 rounded-full bg-white shadow-xs border border-slate-200/60 flex items-center justify-center text-slate-800 mb-3.5">
              <Film className="w-4 h-4 text-[#FF5722]" />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1">
              1080x1920 Portrait Assembly
            </h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Standardized vertical short-form export pre-scaled, letterboxed, and color-tuned for YouTube Shorts and Reels.
            </p>
          </div>
        </div>

        {/* Card 2 */}
        <div className="p-5 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] flex flex-col justify-between">
          <div>
            <div className="w-9 h-9 rounded-full bg-white shadow-xs border border-slate-200/60 flex items-center justify-center text-slate-800 mb-3.5">
              <Zap className="w-4 h-4 text-amber-500" />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1">
              Multimodal Event Detection
            </h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Fuses 16kHz audio RMS energy bursts with OpenCV visual motion velocity and HUD eliminations into calibrated scores.
            </p>
          </div>
        </div>

        {/* Card 3 */}
        <div className="p-5 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] flex flex-col justify-between">
          <div>
            <div className="w-9 h-9 rounded-full bg-white shadow-xs border border-slate-200/60 flex items-center justify-center text-slate-800 mb-3.5">
              <Clock className="w-4 h-4 text-indigo-500" />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1">
              Duration-Budgeted Knapsack
            </h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Solves 2D Weighted Interval Scheduling to guarantee zero clip overlap under your exact duration constraint.
            </p>
          </div>
        </div>

        {/* Card 4 */}
        <div className="p-5 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] flex flex-col justify-between">
          <div>
            <div className="w-9 h-9 rounded-full bg-white shadow-xs border border-slate-200/60 flex items-center justify-center text-slate-800 mb-3.5">
              <Cpu className="w-4 h-4 text-emerald-500" />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1">
              Distributed Redis Streams
            </h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Enterprise job orchestration with transactional outbox, worker lease recovery, and FFmpeg subprocess isolation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
