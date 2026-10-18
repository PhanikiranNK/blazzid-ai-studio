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
    <div className="space-y-2.5">
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
              "flex items-start gap-3.5 p-3 sm:p-3.5 rounded-2xl border transition-all duration-150",
              stepStatus === "current" &&
                "bg-white border-[#FF5722] shadow-sm shadow-orange-500/10 ring-1 ring-[#FF5722]/30",
              stepStatus === "completed" && "bg-white border-[#E5EBE5] shadow-xs",
              stepStatus === "failed" && "bg-rose-50 border-rose-200",
              stepStatus === "cancelled" && "bg-slate-100 border-slate-200",
              stepStatus === "pending" && "opacity-55 border-[#EBF0EB] bg-[#FAFBF9]"
            )}
          >
            {/* Step Icon Indicator */}
            <div className="pt-0.5 flex-shrink-0">
              {stepStatus === "completed" && (
                <div className="w-5 h-5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center">
                  <Check className="w-3 h-3 stroke-[3]" />
                </div>
              )}
              {stepStatus === "current" && (
                <div className="w-5 h-5 rounded-full bg-orange-50 text-[#FF5722] border border-orange-200 flex items-center justify-center animate-pulse">
                  <CircleDot className="w-3 h-3 stroke-[2.5]" />
                </div>
              )}
              {stepStatus === "failed" && (
                <div className="w-5 h-5 rounded-full bg-rose-50 text-rose-600 border border-rose-200 flex items-center justify-center">
                  <AlertTriangle className="w-3 h-3" />
                </div>
              )}
              {stepStatus === "cancelled" && (
                <div className="w-5 h-5 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center">
                  <XCircle className="w-3 h-3" />
                </div>
              )}
              {stepStatus === "pending" && (
                <div className="w-5 h-5 rounded-full bg-slate-100 border border-slate-200 text-slate-400 flex items-center justify-center text-[10px] font-mono font-medium">
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
                    stepStatus === "current" && "text-[#FF5722]",
                    stepStatus === "completed" && "text-slate-900",
                    stepStatus === "failed" && "text-rose-600",
                    stepStatus === "cancelled" && "text-slate-500",
                    stepStatus === "pending" && "text-slate-500"
                  )}
                >
                  {stage.label}
                </span>
                {stepStatus === "current" && (
                  <span className="text-[10px] font-mono text-[#FF5722] font-bold uppercase tracking-wider animate-pulse">
                    Running
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500 leading-normal mt-0.5">
                {stage.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
