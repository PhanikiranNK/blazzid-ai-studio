"use client";

import React, { useEffect, useState, useCallback } from "react";
import { JobResponse } from "@/types/api";
import { api, ApiError } from "@/lib/api";
import { StageProgressStepper } from "./StageProgressStepper";
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  Copy,
  Check,
  AlertOctagon,
  RefreshCw,
  Ban,
  Clock,
} from "lucide-react";
import { formatDuration } from "@/lib/utils";

interface JobProcessingCardProps {
  jobId: string;
  initialJob?: JobResponse | null;
  onJobSucceeded: (job: JobResponse) => void;
  onReset: () => void;
}

export function JobProcessingCard({
  jobId,
  initialJob,
  onJobSucceeded,
  onReset,
}: JobProcessingCardProps) {
  const [job, setJob] = useState<JobResponse | null>(initialJob || null);
  const [copied, setCopied] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [pollError, setPollError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getJobStatus(jobId);
      setJob(data);
      setPollError(null);

      if (data.state === "SUCCEEDED") {
        onJobSucceeded(data);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setPollError(`API Error (${err.status}): ${err.message}`);
      } else {
        setPollError("Connection to backend lost. Retrying...");
      }
    }
  }, [jobId, onJobSucceeded]);

  // Polling loop
  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    let isSubscribed = true;

    const poll = async () => {
      if (!isSubscribed) return;
      await fetchStatus();

      // Check if job reached terminal state
      if (job?.state === "SUCCEEDED" || job?.state === "FAILED" || job?.state === "CANCELLED") {
        return;
      }

      timer = setTimeout(poll, 1500);
    };

    poll();

    return () => {
      isSubscribed = false;
      if (timer) clearTimeout(timer);
    };
  }, [fetchStatus, job?.state]);

  const handleCopyId = () => {
    navigator.clipboard.writeText(jobId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCancel = async () => {
    if (!confirm("Are you sure you want to cancel this highlight generation job?")) {
      return;
    }
    setIsCancelling(true);
    try {
      await api.cancelJob(jobId);
      await fetchStatus();
    } catch (err) {
      alert(`Could not cancel job: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsCancelling(false);
    }
  };

  const getStatusBadge = (state: string) => {
    switch (state) {
      case "SUCCEEDED":
        return <Badge variant="success">SUCCEEDED</Badge>;
      case "PROCESSING":
        return (
          <Badge variant="warning">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            PROCESSING
          </Badge>
        );
      case "QUEUED":
        return <Badge variant="info">QUEUED</Badge>;
      case "FAILED":
        return <Badge variant="danger">FAILED</Badge>;
      case "CANCEL_REQUESTED":
      case "CANCELLED":
        return <Badge variant="outline">CANCELLED</Badge>;
      default:
        return <Badge variant="default">{state}</Badge>;
    }
  };

  return (
    <Card elevated className="w-full max-w-3xl mx-auto overflow-hidden bg-white border border-[#E2E8E2] rounded-[28px] shadow-sm">
      {/* Header */}
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#EEF2EE] pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-base font-bold text-slate-900 tracking-tight">
              Video Highlight Generation
            </h2>
            {job && getStatusBadge(job.state)}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs font-mono text-slate-500">ID: {jobId}</span>
            <button
              onClick={handleCopyId}
              className="text-slate-400 hover:text-slate-700 transition-colors p-1"
              title="Copy Job ID"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-600" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* Top actions */}
        <div className="flex items-center gap-2">
          {job &&
            (job.state === "PROCESSING" || job.state === "QUEUED") && (
              <Button
                variant="danger"
                size="sm"
                onClick={handleCancel}
                isLoading={isCancelling}
              >
                <Ban className="w-3.5 h-3.5" />
                <span>Cancel Edit</span>
              </Button>
            )}

          {job && (job.state === "FAILED" || job.state === "CANCELLED") && (
            <Button variant="outline" size="sm" onClick={onReset}>
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Start Over</span>
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-5">
        {/* Real Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-600 font-semibold">Overall Progress</span>
            <span className="font-mono font-bold text-[#FF5722]">
              {job ? Math.round(job.progress_percent) : 0}%
            </span>
          </div>
          <div className="w-full h-2.5 bg-[#EFF4EF] rounded-full overflow-hidden p-0.5 border border-[#DDE5DD]">
            <div
              className="h-full bg-gradient-to-r from-[#FF5722] to-amber-500 rounded-full transition-all duration-300 shadow-xs"
              style={{ width: `${job ? Math.max(3, job.progress_percent) : 3}%` }}
            />
          </div>
        </div>

        {/* Job Parameters Summary Strip */}
        {job && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] text-xs">
            <div>
              <span className="text-slate-500 block text-[11px] font-medium">Source</span>
              <span className="font-semibold text-slate-900 truncate block mt-0.5" title={job.source_filename}>
                {job.source_filename}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[11px] font-medium">Target Duration</span>
              <span className="font-semibold text-[#FF5722] font-mono block mt-0.5">
                {formatDuration(job.target_duration_sec)}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[11px] font-medium">Format Profile</span>
              <span className="font-semibold text-slate-900 block mt-0.5">
                {job.assembly_profile === "youtube_shorts" ? "9:16 Shorts" : "16:9 Landscape"}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[11px] font-medium">Pipeline Stage</span>
              <span className="font-mono text-teal-700 font-semibold block mt-0.5 truncate">
                {job.stage}
              </span>
            </div>
          </div>
        )}

        {/* Failure Error Alert */}
        {job && job.state === "FAILED" && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-sm text-rose-700">
              <AlertOctagon className="w-4 h-4 flex-shrink-0" />
              <span>Processing Failed ({job.error_code || "ERROR"})</span>
            </div>
            <p className="text-xs text-rose-700 leading-relaxed font-mono">
              {job.error_message || "An unexpected error occurred during pipeline execution."}
            </p>
          </div>
        )}

        {/* Polling Error Toast */}
        {pollError && (
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
            {pollError}
          </div>
        )}

        {/* Pipeline Stage Stepper */}
        {job && (
          <div className="space-y-2 pt-2">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
              Active Stage Pipeline
            </label>
            <StageProgressStepper
              currentStage={job.stage}
              jobState={job.state}
            />
          </div>
        )}
      </CardContent>

      <CardFooter className="flex items-center justify-between text-xs text-slate-500 border-t border-[#EEF2EE] py-3.5">
        <span className="flex items-center gap-1.5 font-mono">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          Retries: {job?.retry_count || 0} / 3
        </span>
        <span className="font-mono text-[11px] text-slate-500">
          Engine: Redis Streams + Worker Pool
        </span>
      </CardFooter>
    </Card>
  );
}
