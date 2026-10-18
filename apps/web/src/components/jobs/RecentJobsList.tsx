"use client";

import React from "react";
import { JobResponse } from "@/types/api";
import { Badge } from "@/components/ui/Badge";
import { Film, Clock, ChevronRight } from "lucide-react";
import { formatDateRelative, formatDuration } from "@/lib/utils";

interface RecentJobsListProps {
  jobs: JobResponse[];
  isLoading: boolean;
  onSelectJob: (job: JobResponse) => void;
}

export function RecentJobsList({
  jobs,
  isLoading,
  onSelectJob,
}: RecentJobsListProps) {
  const getBadge = (state: string) => {
    switch (state) {
      case "SUCCEEDED":
        return <Badge variant="success" size="sm">SUCCEEDED</Badge>;
      case "PROCESSING":
        return (
          <Badge variant="warning" size="sm">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            PROCESSING
          </Badge>
        );
      case "QUEUED":
        return <Badge variant="info" size="sm">QUEUED</Badge>;
      case "FAILED":
        return <Badge variant="danger" size="sm">FAILED</Badge>;
      default:
        return <Badge variant="outline" size="sm">{state}</Badge>;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-bold text-base text-slate-900">Recent Highlights</h3>
          <p className="text-xs text-slate-500">
            Review recent Brawl Stars runs and preview completed montage renders
          </p>
        </div>
        <span className="text-xs text-slate-500 font-mono bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200">
          {jobs.length} jobs
        </span>
      </div>

      <div>
        {isLoading && jobs.length === 0 ? (
          <div className="space-y-2.5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-16 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] animate-pulse"
              />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] text-slate-500 space-y-2">
            <Film className="w-8 h-8 mx-auto text-slate-400" />
            <p className="text-xs font-semibold text-slate-700">No previous jobs submitted yet.</p>
            <p className="text-[11px] text-slate-500">
              Upload a Brawl Stars recording above to start your first edit.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {jobs.map((job, idx) => {
              const numStr = (idx + 1).toString().padStart(2, "0");
              return (
                <button
                  key={job.job_id}
                  type="button"
                  onClick={() => onSelectJob(job)}
                  className="w-full text-left p-4 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] hover:border-[#D5DFD5] hover:bg-[#EEF3EE] transition-all flex items-center justify-between group cursor-pointer shadow-xs"
                >
                  <div className="flex items-center gap-4 min-w-0 flex-1 pr-4">
                    <span className="font-mono text-xs font-bold text-slate-400 w-6 flex-shrink-0">
                      {numStr}
                    </span>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-bold text-sm text-slate-900 truncate max-w-[220px] sm:max-w-md" title={job.source_filename}>
                          {job.source_filename}
                        </span>
                        {getBadge(job.state)}
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-500 font-mono">
                        <span>{job.job_id.slice(0, 8)}...</span>
                        <span>•</span>
                        <span className="text-[#FF5722] font-semibold">{formatDuration(job.target_duration_sec)}</span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-slate-400" />
                          {formatDateRelative(job.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-slate-700 hidden sm:inline group-hover:text-[#FF5722] transition-colors">
                      {job.state === "SUCCEEDED" ? "Preview Montage" : "View Progress"}
                    </span>
                    <div className="w-8 h-8 rounded-full bg-white border border-slate-200/80 flex items-center justify-center text-slate-600 group-hover:text-[#FF5722] group-hover:border-[#FF5722] transition-all shadow-xs">
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
