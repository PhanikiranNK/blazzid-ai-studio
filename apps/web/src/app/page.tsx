"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { VideoDropzone } from "@/components/upload/VideoDropzone";
import { ProfileSelector } from "@/components/upload/ProfileSelector";
import { DurationSlider } from "@/components/upload/DurationSlider";
import { JobProcessingCard } from "@/components/jobs/JobProcessingCard";
import { RecentJobsList } from "@/components/jobs/RecentJobsList";
import { VideoPreviewPlayer } from "@/components/results/VideoPreviewPlayer";
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import {
  AssemblyProfile,
  AspectRatio,
  JobResponse,
  JobResultResponse,
} from "@/types/api";
import { api, ApiError } from "@/lib/api";
import { Sparkles, Film, CheckCircle2, Zap } from "lucide-react";

type ViewMode = "upload" | "processing" | "results";

export default function StudioPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("upload");

  // Form State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<AssemblyProfile>("youtube_shorts");
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("9:16");
  const [duration, setDuration] = useState<number>(30.0);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  // Active Job State
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<JobResponse | null>(null);
  const [jobResultMeta, setJobResultMeta] = useState<JobResultResponse | null>(null);

  // Recent Jobs State
  const [recentJobs, setRecentJobs] = useState<JobResponse[]>([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState<boolean>(false);

  // Server Health State
  const [serverHealth, setServerHealth] = useState<{
    ready: boolean;
    db: boolean;
    redis: boolean;
  }>({
    ready: false,
    db: false,
    redis: false,
  });

  const loadRecentJobs = useCallback(async () => {
    setIsLoadingJobs(true);
    try {
      const resp = await api.listJobs(10, 0);
      setRecentJobs(resp.items);
    } catch {
      // Backend may be starting up
    } finally {
      setIsLoadingJobs(false);
    }
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const h = await api.checkHealth();
      setServerHealth({
        ready: h.status === "ready",
        db: h.database_ready,
        redis: h.redis_ready,
      });
    } catch {
      setServerHealth({ ready: false, db: false, redis: false });
    }
  }, []);

  useEffect(() => {
    let active = true;
    const fetchInitialData = async () => {
      if (!active) return;
      await checkHealth();
      await loadRecentJobs();
    };

    fetchInitialData();
    const interval = setInterval(checkHealth, 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [checkHealth, loadRecentJobs]);

  const handleProfileSelect = (newProfile: AssemblyProfile, newRatio: AspectRatio) => {
    setProfile(newProfile);
    setAspectRatio(newRatio);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setSubmissionError("Please select a valid gameplay recording to process.");
      return;
    }

    setSubmissionError(null);
    setIsSubmitting(true);

    try {
      const newJob = await api.submitJob({
        file: selectedFile,
        target_duration_sec: duration,
        assembly_profile: profile,
        aspect_ratio: aspectRatio,
      });

      setActiveJobId(newJob.job_id);
      setActiveJob(newJob);
      setViewMode("processing");
      loadRecentJobs();
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmissionError(err.message);
      } else {
        setSubmissionError("Failed to submit job. Check server connection.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJobSucceeded = async (succeededJob: JobResponse) => {
    setActiveJob(succeededJob);
    try {
      const res = await api.getJobResult(succeededJob.job_id);
      setJobResultMeta(res);
    } catch {
      // Result manifest can be null if not yet indexed
    }
    setViewMode("results");
    loadRecentJobs();
  };

  const handleSelectRecentJob = async (job: JobResponse) => {
    setActiveJobId(job.job_id);
    setActiveJob(job);
    if (job.state === "SUCCEEDED") {
      try {
        const res = await api.getJobResult(job.job_id);
        setJobResultMeta(res);
      } catch {
        // Result optional
      }
      setViewMode("results");
    } else {
      setViewMode("processing");
    }
  };

  const handleNewEdit = () => {
    setSelectedFile(null);
    setActiveJobId(null);
    setActiveJob(null);
    setJobResultMeta(null);
    setSubmissionError(null);
    setViewMode("upload");
  };

  return (
    <div className="flex min-h-screen bg-[#090b11] text-slate-100 font-sans">
      {/* Sidebar Navigation */}
      <Sidebar serverStatus={serverHealth} />

      {/* Main Studio Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar
          onNewEdit={viewMode !== "upload" ? handleNewEdit : undefined}
          onRefresh={loadRecentJobs}
          isRefreshing={isLoadingJobs}
        />

        <main className="flex-1 p-6 sm:p-8 max-w-7xl w-full mx-auto space-y-8">
          {/* UPLOAD VIEW */}
          {viewMode === "upload" && (
            <div className="space-y-8 animate-in fade-in duration-200">
              {/* Studio Hero Header */}
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-[#141826] via-[#121622] to-[#161a29] border border-[#22283d] shadow-lg shadow-black/30">
                <div className="space-y-1.5">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-semibold">
                    <Zap className="w-3.5 h-3.5 fill-current" />
                    Stage 5 Distributed Engine Active
                  </div>
                  <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                    Transform Long Gameplay into Viral Highlights
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-400 max-w-xl">
                    Our AI pipeline ingests your raw match recording, pinpoints high-intensity
                    combat bursts, and optimizes a duration-budgeted montage rendered directly via FFmpeg.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>CV Motion Density</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Audio Burst Detector</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Dynamic Knapsack</span>
                  </div>
                </div>
              </div>

              {/* Upload & Configuration Form */}
              <form onSubmit={handleSubmit}>
                <Card elevated className="overflow-hidden">
                  <CardHeader className="py-4">
                    <div className="flex items-center gap-2">
                      <Film className="w-4 h-4 text-amber-400" />
                      <h3 className="font-bold text-sm text-white">
                        Create New Highlight Montage
                      </h3>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-6">
                    {/* Video Upload Dropzone with Live Preview */}
                    <VideoDropzone
                      file={selectedFile}
                      onFileSelect={setSelectedFile}
                    />

                    {/* Output Format Profile Selector */}
                    <ProfileSelector
                      selectedProfile={profile}
                      selectedAspectRatio={aspectRatio}
                      onSelect={handleProfileSelect}
                    />

                    {/* Target Duration Slider & Presets */}
                    <DurationSlider
                      duration={duration}
                      onChange={setDuration}
                    />

                    {/* Error Banner */}
                    {submissionError && (
                      <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-medium">
                        {submissionError}
                      </div>
                    )}
                  </CardContent>

                  <CardFooter className="flex flex-col sm:flex-row items-center justify-between gap-4 py-4">
                    <div className="text-xs text-slate-400">
                      Target Duration:{" "}
                      <span className="font-bold text-amber-400 font-mono">
                        {Math.round(duration)}s
                      </span>{" "}
                      • Profile:{" "}
                      <span className="font-bold text-slate-200">
                        {profile === "youtube_shorts" ? "9:16 Vertical" : "16:9 Landscape"}
                      </span>
                    </div>

                    <Button
                      type="submit"
                      variant="primary"
                      size="lg"
                      isLoading={isSubmitting}
                      disabled={!selectedFile}
                      className="w-full sm:w-auto"
                    >
                      <Sparkles className="w-4 h-4 fill-current" />
                      <span>Generate Highlights</span>
                    </Button>
                  </CardFooter>
                </Card>
              </form>

              {/* Recent Jobs History Section */}
              <div id="jobs">
                <RecentJobsList
                  jobs={recentJobs}
                  isLoading={isLoadingJobs}
                  onSelectJob={handleSelectRecentJob}
                />
              </div>
            </div>
          )}

          {/* PROCESSING VIEW */}
          {viewMode === "processing" && activeJobId && (
            <div className="animate-in fade-in duration-200 space-y-6">
              <JobProcessingCard
                jobId={activeJobId}
                initialJob={activeJob}
                onJobSucceeded={handleJobSucceeded}
                onReset={handleNewEdit}
              />
            </div>
          )}

          {/* RESULTS VIEW */}
          {viewMode === "results" && activeJob && (
            <div className="animate-in fade-in duration-200 space-y-6">
              <VideoPreviewPlayer
                job={activeJob}
                resultMeta={jobResultMeta}
                onNewEdit={handleNewEdit}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
