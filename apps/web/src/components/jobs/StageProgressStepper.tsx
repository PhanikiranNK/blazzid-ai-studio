"use client";

import React from "react";
import { JobStage, JobState } from "@/types/api";
import { Check, CircleDot, AlertTriangle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface StageProgressStepperProps {
  currentStage: JobStage;
  jobState: JobState;
}

interface StageStep {
  id: JobStage;
  label: string;
  description: string;
}

const PIPELINE_STAGES: StageStep[] = [
  {
    id: "VALIDATING_INPUT",
    label: "Input Integrity",
    description: "Probing video containers, streams & audio channels",
  },
  {
    id: "PREPROCESSING",
    label: "Media Ingestion",
    description: "Extracting audio waveform & standardized proxy frames",
  },
  {
    id: "DETECTING_EVENTS",
    label: "Gameplay Analysis",
    description: "Detecting combat bursts, eliminations & visual velocity",
  },
  {
    id: "RANKING_HIGHLIGHTS",
    label: "Highlight Ranking",
    description: "Scoring candidate moments with explainable weights",
  },
  {
    id: "PLANNING_EDIT",
    label: "Budget Optimization",
    description: "Solving knapsack selection under target duration",
  },
  {
    id: "RENDERING",
    label: "FFmpeg Assembly",
    description: "Trimming, scaling to 1080x1920 & hardware encoding",
  },
  {
    id: "FINALIZING",
    label: "Artifact Packaging",
    description: "Generating manifest & persisting highlight montage",
  },
];

export function StageProgressStepper({
  currentStage,
  jobState,
}: StageProgressStepperProps) {
  const stageOrder = PIPELINE_STAGES.map((s) => s.id);
  const currentIndex = stageOrder.indexOf(currentStage);

  const isFailed = jobState === "FAILED";
  const isCancelled = jobState === "CANCELLED" || jobState === "CANCEL_REQUESTED";
  const isSucceeded = jobState === "SUCCEEDED";

  return (
    <div className="space-y-3">
      {PIPELINE_STAGES.map((stage, idx) => {
        let stepStatus: "completed" | "current" | "pending" | "failed" | "cancelled" =
          "pending";

        if (isSucceeded) {
          stepStatus = "completed";
        } else if (isFailed && idx === currentIndex) {
          stepStatus = "failed";
        } else if (isCancelled && idx === currentIndex) {
          stepStatus = "cancelled";
        } else if (idx < currentIndex) {
          stepStatus = "completed";
        } else if (idx === currentIndex) {
          stepStatus = "current";
        } else {
          stepStatus = "pending";
        }

        return (
          <div
            key={stage.id}
            className={cn(
              "flex items-start gap-3.5 p-3 rounded-xl border transition-all duration-150",
              stepStatus === "current" &&
                "bg-[#171c2b] border-amber-500/50 shadow-md shadow-amber-500/5",
              stepStatus === "completed" && "bg-[#111420]/60 border-[#1a1f30]",
              stepStatus === "failed" && "bg-rose-500/10 border-rose-500/30",
              stepStatus === "cancelled" && "bg-slate-800/20 border-slate-700/40",
              stepStatus === "pending" && "opacity-50 border-transparent bg-transparent"
            )}
          >
            {/* Step Icon Indicator */}
            <div className="pt-0.5 flex-shrink-0">
              {stepStatus === "completed" && (
                <div className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center">
                  <Check className="w-3 h-3 stroke-[2.5]" />
                </div>
              )}
              {stepStatus === "current" && (
                <div className="w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40 flex items-center justify-center animate-pulse">
                  <CircleDot className="w-3 h-3" />
                </div>
              )}
              {stepStatus === "failed" && (
                <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center">
                  <AlertTriangle className="w-3 h-3" />
                </div>
              )}
              {stepStatus === "cancelled" && (
                <div className="w-5 h-5 rounded-full bg-slate-700 text-slate-400 flex items-center justify-center">
                  <XCircle className="w-3 h-3" />
                </div>
              )}
              {stepStatus === "pending" && (
                <div className="w-5 h-5 rounded-full bg-[#181d2c] border border-[#262f48] text-slate-500 flex items-center justify-center text-[10px] font-mono">
                  {idx + 1}
                </div>
              )}
            </div>

            {/* Step Label and Description */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    "text-xs font-bold",
                    stepStatus === "current" && "text-amber-400",
                    stepStatus === "completed" && "text-slate-200",
                    stepStatus === "failed" && "text-rose-400",
                    stepStatus === "cancelled" && "text-slate-400",
                    stepStatus === "pending" && "text-slate-500"
                  )}
                >
                  {stage.label}
                </span>
                {stepStatus === "current" && (
                  <span className="text-[10px] font-mono text-amber-400 font-semibold uppercase tracking-wider animate-pulse">
                    Running
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 leading-normal mt-0.5">
                {stage.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
