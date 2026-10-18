"use client";

import React, { useRef, useState, useEffect } from "react";
import { UploadCloud, Film, X, AlertCircle } from "lucide-react";
import { formatBytes, formatDuration, cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";

interface VideoDropzoneProps {
  file: File | null;
  onFileSelect: (file: File | null) => void;
  maxSizeBytes?: number;
}

export function VideoDropzone({
  file,
  onFileSelect,
  maxSizeBytes = 500 * 1024 * 1024, // 500MB
}: VideoDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [mediaMeta, setMediaMeta] = useState<{
    duration: number;
    width: number;
    height: number;
  } | null>(null);


  const inputRef = useRef<HTMLInputElement>(null);


  // Manage object URL lifecycle with useMemo
  const previewUrl = React.useMemo(() => {
    if (!file) return null;
    try {
      return URL.createObjectURL(file);
    } catch {
      return null;
    }
  }, [file]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const validateAndSelect = (selectedFile: File) => {
    setErrorMessage(null);

    // Validate size
    if (selectedFile.size > maxSizeBytes) {
      setErrorMessage(
        `File size (${formatBytes(selectedFile.size)}) exceeds the maximum allowed limit of ${formatBytes(maxSizeBytes)}.`
      );
      return;
    }

    // Validate extension / MIME
    const name = selectedFile.name || "";
    const ext = name.split(".").pop()?.toLowerCase();
    const validExtensions = ["mp4", "mov", "mkv", "webm", "m4v"];
    const isVideoMime = selectedFile.type.startsWith("video/");

    if (!isVideoMime && (!ext || !validExtensions.includes(ext))) {
      setErrorMessage(
        `Unsupported video format ".${ext || "unknown"}". Supported formats: MP4, MOV, MKV, WEBM.`
      );
      return;
    }

    onFileSelect(selectedFile);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelect(e.dataTransfer.files[0]);
    }
  };

  const handleLoadedMetadata = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget;
    setMediaMeta({
      duration: video.duration,
      width: video.videoWidth,
      height: video.videoHeight,
    });
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onFileSelect(null);
    setErrorMessage(null);
    setMediaMeta(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const handleBrowseClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    inputRef.current?.click();
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
          Source Gameplay Recording
        </label>
        <span className="text-[11px] text-slate-500 font-mono">
          Max {formatBytes(maxSizeBytes)}
        </span>
      </div>

      {/* Hidden file input */}
      <input
        id="video-file-input"
        ref={inputRef}
        type="file"
        accept="video/*,.mp4,.mov,.mkv,.webm,video/mp4,video/quicktime,video/x-matroska,video/webm"
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            validateAndSelect(e.target.files[0]);
          }
          // Reset so re-selecting the same file fires onChange
          e.target.value = "";
        }}
      />

      {/* When File is Selected: Interactive Preview */}
      {file ? (
        <div className="p-4 sm:p-5 rounded-2xl bg-white border border-[#E2E8E2] shadow-xs space-y-4">
          <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
            {/* Embedded video preview thumbnail */}
            <div className="relative w-full md:w-56 h-32 rounded-xl bg-slate-950 overflow-hidden border border-slate-200 flex-shrink-0 flex items-center justify-center">
              {previewUrl ? (
                <video
                  src={previewUrl}
                  onLoadedMetadata={handleLoadedMetadata}
                  className="w-full h-full object-contain"
                  muted
                  controls={false}
                />
              ) : (
                <Film className="w-10 h-10 text-slate-600" />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent pointer-events-none" />
              {mediaMeta && (
                <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 font-mono text-[10px] text-white font-bold">
                  {formatDuration(mediaMeta.duration)}
                </div>
              )}
            </div>

            {/* Video Details */}
            <div className="flex-1 min-w-0 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="font-bold text-sm text-slate-900 truncate" title={file.name}>
                      {file.name}
                    </h4>
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                      Ready
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">
                    {formatBytes(file.size)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRemove}
                  className="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg"
                  title="Remove video"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>

              {/* Resolution and codec chip */}
              <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
                {mediaMeta ? (
                  <>
                    <span className="px-2.5 py-0.5 rounded-full bg-slate-100 border border-slate-200/80 font-mono text-[11px] text-slate-700 font-semibold">
                      {mediaMeta.width}x{mediaMeta.height}
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full bg-orange-50 border border-orange-200/80 font-mono text-[11px] text-[#FF5722] font-semibold">
                      {mediaMeta.width > mediaMeta.height ? "Landscape (16:9)" : "Portrait (9:16)"}
                    </span>
                  </>
                ) : (
                  <span className="text-slate-400 text-xs italic">
                    Reading media metadata...
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 pt-1">
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  onClick={handleBrowseClick}
                  className="text-xs py-1"
                >
                  Replace Video
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Empty Dropzone with Native Label + Drag & Drop */
        <label
          htmlFor="video-file-input"
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={cn(
            "p-8 sm:p-10 rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer flex flex-col items-center justify-center text-center gap-3 select-none group block",
            isDragOver
              ? "bg-orange-50/50 border-[#FF5722] scale-[0.99] shadow-sm"
              : "bg-[#F9FAF9] border-[#D4DDD4] hover:border-[#FF5722] hover:bg-orange-50/15"
          )}
        >
          <div
            className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center transition-transform group-hover:scale-105 duration-200 bg-white shadow-xs border border-slate-200/80 pointer-events-none",
              isDragOver ? "text-[#FF5722] border-[#FF5722]" : "text-slate-600 group-hover:text-[#FF5722]"
            )}
          >
            <UploadCloud className="w-6 h-6" />
          </div>

          <div className="space-y-1 pointer-events-none">
            <p className="font-bold text-sm text-slate-900">
              Drag & drop gaming video, or{" "}
              <span className="text-[#FF5722] underline decoration-[#FF5722]/40 underline-offset-2">
                browse files
              </span>
            </p>
            <p className="text-xs text-slate-500">
              Supports Brawl Stars recordings up to 500MB (MP4, MOV, MKV, WEBM)
            </p>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono pt-1 pointer-events-none">
            <span className="flex items-center gap-1">
              <Film className="w-3 h-3 text-slate-400" />
              1080p / 60fps recommended
            </span>
          </div>
        </label>
      )}

      {/* Validation Error Banner */}
      {errorMessage && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
}
