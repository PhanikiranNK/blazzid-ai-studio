"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { VideoDropzone } from "@/components/upload/VideoDropzone";
import { ProfileSelector } from "@/components/upload/ProfileSelector";
import { DurationSlider } from "@/components/upload/DurationSlider";
import { ViralEffectsSelector, ViralEffectsState } from "@/components/upload/ViralEffectsSelector";
import { JobProcessingCard } from "@/components/jobs/JobProcessingCard";
import { RecentJobsList } from "@/components/jobs/RecentJobsList";
import { VideoPreviewPlayer } from "@/components/results/VideoPreviewPlayer";
import { StudioBentoCards } from "@/components/studio/StudioBentoCards";
import {
  AssemblyProfile,
  AspectRatio,
  JobResponse,
  JobResultResponse,
} from "@/types/api";
import { api, ApiError } from "@/lib/api";
import {
  Sparkles,
  Film,
  ChevronRight,
  ArrowRight,
  MapPin,
  History,
  BookOpen,
  Layers,
  Wand2,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";

type ViewMode = "upload" | "processing" | "results";
type ActiveTab = "overview" | "workspace" | "highlights" | "recent" | "specs";

export default function StudioPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("upload");
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [showFullOverview, setShowFullOverview] = useState(false);

  // Form State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<AssemblyProfile>("youtube_shorts");
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("9:16");
  const [duration, setDuration] = useState<number>(30.0);
  const [viralEffects, setViralEffects] = useState<ViralEffectsState>({
    autoZoom: true,
    memeOverlays: true,
    soundtrack: "phonk",
  });
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

  const uploadFormRef = useRef<HTMLDivElement>(null);

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

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    if (!selectedFile) {
      setSubmissionError(
        "No video selected yet. Please drag & drop or browse for a gameplay recording (MP4, MOV, MKV, WEBM) above."
      );
      if (uploadFormRef.current) {
        uploadFormRef.current.scrollIntoView({ behavior: "smooth" });
      }
      return;
    }


    setSubmissionError(null);
    setIsSubmitting(true);

    try {
      let compositeProfile = profile;
      const flags: string[] = [];
      if (viralEffects.autoZoom) flags.push("zoom");
      if (viralEffects.memeOverlays) flags.push("meme");
      if (viralEffects.soundtrack && viralEffects.soundtrack !== "none") {
        flags.push(viralEffects.soundtrack);
      }
      if (flags.length > 0) {
        compositeProfile = `${profile}:${flags.join(":")}` as AssemblyProfile;
      }

      const newJob = await api.submitJob({
        file: selectedFile,
        target_duration_sec: duration,
        assembly_profile: compositeProfile,
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
    setActiveTab("overview");
  };

  const scrollToSection = (id: string, tab: ActiveTab) => {
    setActiveTab(tab);
    if (viewMode !== "upload") {
      setViewMode("upload");
    }
    setTimeout(() => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth" });
      }
    }, 50);
  };

  return (
    <div className="flex min-h-screen bg-[#E8EFE9] text-slate-900 font-sans antialiased selection:bg-[#FF5722] selection:text-white">
      {/* Vertical Icon Rail Dock Navigation */}
      <Sidebar serverStatus={serverHealth} />

      {/* Main Content Viewport */}
      <div className="flex-1 flex flex-col min-w-0 p-3 sm:p-6 lg:p-8 max-w-[1400px] mx-auto w-full">
        {/* Elevated White Workspace Card (Dribbble Reference Frame) */}
        <div className="bg-white rounded-[28px] sm:rounded-[36px] border border-[#D5DFD5] shadow-xs p-5 sm:p-8 lg:p-10 flex flex-col gap-8 transition-all">
          {/* Breadcrumb Navigation */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
              <span className="hover:text-slate-800 transition-colors cursor-pointer" onClick={handleNewEdit}>
                Find Highlights
              </span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-slate-900 font-bold">
                Brawl Stars Montage Engine
              </span>
            </div>

            <button
              onClick={loadRecentJobs}
              className="text-slate-400 hover:text-slate-700 transition-colors p-1 rounded-full hover:bg-slate-100"
              title="Refresh job status"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isLoadingJobs && "animate-spin text-[#FF5722]")} />
            </button>
          </div>

          {/* Program Header Block (Emblem, Title, Version Pill, Right CTA) */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-2 border-b border-[#EEF2EE]">
            {/* Left Header: Avatar + Title Info */}
            <div className="flex items-center gap-4 sm:gap-5">
              <div className="w-14 h-14 rounded-full bg-[#D7EFE6] text-teal-800 border border-[#BDE3D5] flex items-center justify-center font-bold text-xl shadow-xs flex-shrink-0">
                <Sparkles className="w-6 h-6 text-teal-700" />
              </div>

              <div className="space-y-1">
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                    Brawl Stars Highlight Montage
                  </h1>
                  <span className="bg-[#EFF2F0] text-slate-700 text-xs font-semibold px-2.5 py-0.5 rounded-full border border-[#D5DFD5]">
                    v5.1 Distributed
                  </span>
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
                  <span className="font-semibold text-slate-700">BLAZZID AI Studio</span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    FastAPI + Redis Streams
                  </span>
                  <span>•</span>
                  <span className="text-[#FF5722] font-semibold">Zero Overlap Knapsack</span>
                </div>
              </div>
            </div>

            {/* Right Header: Pricing / Speed Stat + Coral Pill CTA Button */}
            <div className="flex items-center gap-5 justify-between md:justify-end">
              <div className="text-right">
                <span className="text-xs text-slate-500 block font-medium">Processing Speed</span>
                <span className="text-lg sm:text-xl font-black text-slate-900 font-mono tracking-tight">
                  ~92x Realtime
                </span>
              </div>

              {viewMode === "upload" ? (
                <button
                  type="button"
                  onClick={() => handleSubmit()}
                  disabled={isSubmitting}
                  className="bg-[#FF5722] hover:bg-[#E84A1A] active:scale-95 disabled:opacity-70 text-white px-5 sm:px-6 py-2.5 rounded-full font-bold text-xs sm:text-sm shadow-md shadow-orange-500/20 flex items-center gap-2 transition-all cursor-pointer"
                >
                  <span>{selectedFile ? "Generate Highlights" : "Upload Video"}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleNewEdit}
                  className="bg-[#FF5722] hover:bg-[#E84A1A] active:scale-95 text-white px-5 sm:px-6 py-2.5 rounded-full font-bold text-xs sm:text-sm shadow-md shadow-orange-500/20 flex items-center gap-2 transition-all cursor-pointer"
                >
                  <span>New Highlight</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Segmented Horizontal Pill Navigation Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs font-semibold">
            <button
              type="button"
              onClick={() => scrollToSection("overview-section", "overview")}
              className={cn(
                "px-4 py-2 rounded-xl transition-all cursor-pointer flex items-center gap-2 flex-shrink-0",
                activeTab === "overview" && viewMode === "upload"
                  ? "bg-[#18191B] text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/80"
              )}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Overview</span>
            </button>

            <button
              type="button"
              onClick={() => scrollToSection("workspace-section", "workspace")}
              className={cn(
                "px-4 py-2 rounded-xl transition-all cursor-pointer flex items-center gap-2 flex-shrink-0",
                activeTab === "workspace" && viewMode === "upload"
                  ? "bg-[#18191B] text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/80"
              )}
            >
              <Wand2 className="w-3.5 h-3.5" />
              <span>Highlight Studio</span>
            </button>

            <button
              type="button"
              onClick={() => scrollToSection("highlights-section", "highlights")}
              className={cn(
                "px-4 py-2 rounded-xl transition-all cursor-pointer flex items-center gap-2 flex-shrink-0",
                activeTab === "highlights" && viewMode === "upload"
                  ? "bg-[#18191B] text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/80"
              )}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Pipeline Highlights</span>
            </button>

            <button
              type="button"
              onClick={() => scrollToSection("jobs-section", "recent")}
              className={cn(
                "px-4 py-2 rounded-xl transition-all cursor-pointer flex items-center gap-2 flex-shrink-0",
                activeTab === "recent" && viewMode === "upload"
                  ? "bg-[#18191B] text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/80"
              )}
            >
              <History className="w-3.5 h-3.5" />
              <span>Recent Jobs</span>
            </button>
          </div>

          {/* UPLOAD & STUDIO OVERVIEW MODE */}
          {viewMode === "upload" && (
            <div className="space-y-10 animate-in fade-in duration-200">
              {/* Program Overview Paragraph */}
              <div id="overview-section" className="space-y-2">
                <h3 className="text-sm font-bold text-slate-900">
                  Program Overview
                </h3>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed max-w-4xl">
                  The Brawl Stars Montage Engine at BLAZZID AI Studio is an intelligent video editing system designed for creators and competitive players. It ingests your raw match recordings, pinpoints peak-intensity combat bursts and eliminations using synchronized audio RMS and computer vision velocity, and solves dynamic knapsack interval scheduling to assemble a duration-budgeted montage rendered directly via hardware-accelerated FFmpeg.{" "}
                  {showFullOverview ? (
                    <span>
                      The system features complete worker isolation, transactional outbox staging, Redis Streams dispatching, and zero clip overlap guarantees for broadcast-ready shorts.
                    </span>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => setShowFullOverview(!showFullOverview)}
                    className="font-bold text-slate-900 hover:text-[#FF5722] ml-1.5 transition-colors cursor-pointer"
                  >
                    {showFullOverview ? "Read less" : "Read more..."}
                  </button>
                </p>
              </div>

              {/* Bento Grid: Program Highlights */}
              <div id="highlights-section">
                <StudioBentoCards />
              </div>

              {/* Interactive Studio Workspace Form */}
              <div id="workspace-section" ref={uploadFormRef} className="space-y-6 pt-2">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <Film className="w-4 h-4 text-[#FF5722]" />
                      Studio Workspace
                    </h3>
                    <p className="text-xs text-slate-500">
                      Upload your raw match, choose format profile, and configure montage duration
                    </p>
                  </div>

                  <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-slate-500">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span>Engine Ready</span>
                  </div>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                  {/* Video Dropzone */}
                  <VideoDropzone
                    file={selectedFile}
                    onFileSelect={(f) => {
                      setSelectedFile(f);
                      if (f) setSubmissionError(null);
                    }}
                  />

                  {/* Profile Selector */}
                  <ProfileSelector
                    selectedProfile={profile}
                    selectedAspectRatio={aspectRatio}
                    onSelect={handleProfileSelect}
                  />

                  {/* Duration Slider */}
                  <DurationSlider
                    duration={duration}
                    onChange={setDuration}
                  />

                  {/* Viral Edit Enhancements (Auto-Zoom, Memes, Trending Music) */}
                  <ViralEffectsSelector
                    effects={viralEffects}
                    onChange={setViralEffects}
                  />

                  {/* Submission Error Banner */}
                  {submissionError && (
                    <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold">
                      {submissionError}
                    </div>
                  )}

                  {/* Form Actions Footer */}
                  <div className="p-4 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] flex flex-col sm:flex-row items-center justify-between gap-4">
                    <div className="text-xs text-slate-600 flex items-center gap-3 flex-wrap">
                      {selectedFile ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] font-semibold">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          <span className="truncate max-w-[140px]" title={selectedFile.name}>
                            {selectedFile.name}
                          </span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-[11px] font-semibold">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                          <span>No Video Attached</span>
                        </span>
                      )}
                      <span>•</span>
                      <span>
                        Target:{" "}
                        <strong className="text-[#FF5722] font-mono">
                          {Math.round(duration)}s
                        </strong>
                      </span>
                      <span>•</span>
                      <span>
                        Profile:{" "}
                        <strong className="text-slate-900">
                          {profile === "youtube_shorts" ? "9:16 Shorts" : "16:9 Landscape"}
                        </strong>
                      </span>
                      <span>•</span>
                      <span className="text-[11px] text-slate-500 font-medium">
                        FX:{" "}
                        <span className="text-[#FF5722] font-semibold">
                          {[
                            viralEffects.autoZoom && "Auto-Zoom",
                            viralEffects.memeOverlays && "Memes",
                            viralEffects.soundtrack !== "none" &&
                              `${viralEffects.soundtrack.toUpperCase()} BGM`,
                          ]
                            .filter(Boolean)
                            .join(" + ") || "Raw Audio"}
                        </span>
                      </span>
                    </div>

                    <button
                      type="submit"
                      disabled={isSubmitting}
                      onClick={(e) => {
                        if (!selectedFile) {
                          e.preventDefault();
                          setSubmissionError(
                            "No video selected yet. Please drag & drop or browse for a gameplay recording (MP4, MOV, MKV, WEBM) above."
                          );
                          if (uploadFormRef.current) {
                            uploadFormRef.current.scrollIntoView({ behavior: "smooth" });
                          }
                        }
                      }}
                      className={cn(
                        "w-full sm:w-auto px-6 py-2.5 rounded-full font-bold text-xs sm:text-sm shadow-md flex items-center justify-center gap-2 transition-all cursor-pointer",
                        selectedFile
                          ? "bg-[#FF5722] hover:bg-[#E84A1A] text-white shadow-orange-500/20 active:scale-95"
                          : "bg-slate-200 hover:bg-slate-300 text-slate-700 shadow-none"
                      )}
                    >
                      <Sparkles className="w-4 h-4 fill-current" />
                      <span>
                        {isSubmitting
                          ? "Submitting Pipeline..."
                          : selectedFile
                          ? "Generate Highlights"
                          : "Select Video First"}
                      </span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>
                </form>
              </div>

              {/* Recent Jobs History (Curriculum Style) */}
              <div id="jobs-section" className="pt-2">
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
        </div>
      </div>
    </div>
  );
}
