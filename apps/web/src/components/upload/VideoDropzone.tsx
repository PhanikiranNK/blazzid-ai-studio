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
        <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
          Source Gameplay Recording
        </label>
        <span className="text-[11px] text-slate-400 font-mono">
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
      {file && previewUrl ? (
        <div className="p-4 rounded-2xl bg-[#141826] border border-[#23293d] space-y-4">
          <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
            {/* Embedded video preview thumbnail */}
            <div className="relative w-full md:w-56 h-32 rounded-xl bg-black overflow-hidden border border-[#2b334d] flex-shrink-0">
              <video
                src={previewUrl}
                onLoadedMetadata={handleLoadedMetadata}
                className="w-full h-full object-contain"
                muted
                controls={false}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent pointer-events-none" />
              {mediaMeta && (
                <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 font-mono text-[10px] text-amber-400 font-bold border border-amber-500/30">
                  {formatDuration(mediaMeta.duration)}
                </div>
              )}
            </div>

            {/* Video Details */}
            <div className="flex-1 min-w-0 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h4 className="font-bold text-sm text-white truncate" title={file.name}>
                    {file.name}
                  </h4>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">
                    {formatBytes(file.size)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRemove}
                  className="text-slate-400 hover:text-rose-400 p-1.5"
                  title="Remove video"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>

              {/* Resolution and codec chip */}
              <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-slate-300">
                {mediaMeta ? (
                  <>
                    <span className="px-2 py-0.5 rounded bg-[#1c2235] border border-[#28314a] font-mono text-[11px] text-slate-300">
                      {mediaMeta.width}x{mediaMeta.height}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-[#1c2235] border border-[#28314a] font-mono text-[11px] text-indigo-400">
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
                  variant="outline"
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
            "p-8 rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer flex flex-col items-center justify-center text-center gap-3 select-none group block",
            isDragOver
              ? "bg-amber-500/10 border-amber-500 scale-[0.99] shadow-xl shadow-amber-500/10 ring-2 ring-amber-500/20"
              : "bg-[#111420] border-[#22283d] hover:border-[#384263] hover:bg-[#141826]"
          )}
        >
          <div
            className={cn(
              "w-14 h-14 rounded-2xl flex items-center justify-center transition-transform group-hover:scale-105 duration-200",
              isDragOver
                ? "bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/30"
                : "bg-[#181d2c] text-slate-400 group-hover:text-amber-400 group-hover:bg-[#1f2538]"
            )}
          >
            <UploadCloud className="w-7 h-7" />
          </div>

          <div className="space-y-1">
            <p className="font-bold text-sm text-white">
              Drag & drop gaming video, or{" "}
              <span className="text-amber-400 underline decoration-amber-500/50 underline-offset-2">
                browse files
              </span>
            </p>
            <p className="text-xs text-slate-400">
              Supports Brawl Stars recordings up to 500MB (MP4, MOV, MKV, WEBM)
            </p>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono pt-1">
            <span className="flex items-center gap-1">
              <Film className="w-3 h-3 text-slate-500" />
              1080p / 60fps recommended
            </span>
          </div>
        </label>
      )}

      {/* Validation Error Banner */}
      {errorMessage && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-medium">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
}
