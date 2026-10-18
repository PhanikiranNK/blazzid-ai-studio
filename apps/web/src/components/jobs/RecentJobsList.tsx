"use client";

import React from "react";
import { JobResponse } from "@/types/api";
import { Card, CardHeader, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Film, Clock, ChevronRight, History } from "lucide-react";
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
    <Card className="overflow-hidden">
      <CardHeader className="flex items-center justify-between py-4">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-amber-400" />
          <h3 className="font-bold text-sm text-white">Recent Highlight Jobs</h3>
        </div>
        <span className="text-xs text-slate-400 font-mono">
          {jobs.length} total
        </span>
      </CardHeader>

      <CardContent className="p-0">
        {isLoading && jobs.length === 0 ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 rounded-xl bg-[#171b29] animate-pulse"
              />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center text-slate-400 space-y-2">
            <Film className="w-8 h-8 mx-auto text-slate-600" />
            <p className="text-xs font-medium">No previous jobs submitted yet.</p>
            <p className="text-[11px] text-slate-500">
              Upload a Brawl Stars recording above to start your first edit.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[#1a1f30]">
            {jobs.map((job) => (
              <button
                key={job.job_id}
                type="button"
                onClick={() => onSelectJob(job)}
                className="w-full text-left p-4 hover:bg-[#161a28] transition-colors flex items-center justify-between group cursor-pointer"
              >
                <div className="min-w-0 flex-1 pr-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-xs text-white truncate max-w-[200px] sm:max-w-xs" title={job.source_filename}>
                      {job.source_filename}
                    </span>
                    {getBadge(job.state)}
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono">
                    <span>{job.job_id}</span>
                    <span>•</span>
                    <span>{formatDuration(job.target_duration_sec)}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-500" />
                      {formatDateRelative(job.created_at)}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-slate-500 group-hover:text-amber-400 transition-colors">
                  <span className="text-xs font-semibold hidden sm:inline">
                    {job.state === "SUCCEEDED" ? "Preview" : "View"}
                  </span>
                  <ChevronRight className="w-4 h-4" />
                </div>
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
