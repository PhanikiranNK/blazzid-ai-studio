"use client";

import React, { useState } from "react";
import { JobResponse, JobResultResponse } from "@/types/api";
import { api } from "@/lib/api";
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  Download,
  FileCode,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { formatDuration, cn } from "@/lib/utils";

interface VideoPreviewPlayerProps {
  job: JobResponse;
  resultMeta?: JobResultResponse | null;
  onNewEdit: () => void;
}

export function VideoPreviewPlayer({
  job,
  resultMeta,
  onNewEdit,
}: VideoPreviewPlayerProps) {
  const [downloading, setDownloading] = useState(false);

  const videoUrl = api.getArtifactUrl(job.job_id, "rendered_montage");
  const manifestUrl = api.getArtifactUrl(job.job_id, "edit_manifest_json");

  const isPortrait = job.aspect_ratio === "9:16" || job.assembly_profile === "youtube_shorts";

  const handleDownloadVideo = () => {
    setDownloading(true);
    const link = document.createElement("a");
    link.href = videoUrl;
    link.download = `${job.job_id}_highlight.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => setDownloading(false), 1000);
  };

  const handleDownloadManifest = () => {
    const link = document.createElement("a");
    link.href = manifestUrl;
    link.download = `${job.job_id}_edit_manifest.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Card elevated className="w-full max-w-4xl mx-auto overflow-hidden bg-white border border-[#E2E8E2] rounded-[28px] shadow-sm">
      {/* Header */}
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#EEF2EE] pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#FF5722]" />
              Generated Highlight Montage
            </h2>
            <Badge variant="success">READY</Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Processed from <span className="text-slate-800 font-semibold">{job.source_filename}</span>
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={onNewEdit}>
            <RefreshCw className="w-3.5 h-3.5" />
            <span>New Edit</span>
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={handleDownloadVideo}
            isLoading={downloading}
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download MP4</span>
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-5">
        {/* Video Player Container */}
        <div className="flex justify-center bg-[#F4F7F4] rounded-2xl p-4 sm:p-6 border border-[#E0E7E0]">
          <div
            className={cn(
              "relative rounded-xl overflow-hidden shadow-lg border border-slate-300/80 bg-black",
              isPortrait
                ? "w-full max-w-xs aspect-[9/16]"
                : "w-full max-w-2xl aspect-video"
            )}
          >
            <video
              src={videoUrl}
              controls
              autoPlay
              playsInline
              className="w-full h-full object-contain"
            />
          </div>
        </div>

        {/* Video Summary Chips */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] text-xs">
          <div>
            <span className="text-slate-500 block text-[11px] font-medium">Format / Ratio</span>
            <span className="font-bold text-slate-900 block mt-0.5">
              {isPortrait ? "9:16 Vertical (1080x1920)" : "16:9 Landscape (1920x1080)"}
            </span>
          </div>

          <div>
            <span className="text-slate-500 block text-[11px] font-medium">Output Duration</span>
            <span className="font-mono font-bold text-[#FF5722] block mt-0.5">
              {formatDuration(job.target_duration_sec)}
            </span>
          </div>

          <div>
            <span className="text-slate-500 block text-[11px] font-medium">Selected Clips</span>
            <span className="font-bold text-teal-700 font-mono block mt-0.5">
              {resultMeta?.manifest?.clips?.length || "Auto-Selected"} moments
            </span>
          </div>

          <div>
            <span className="text-slate-500 block text-[11px] font-medium">Assembly Codec</span>
            <span className="font-mono text-slate-800 block mt-0.5">
              H.264 / AAC 60fps
            </span>
          </div>
        </div>

        {/* Timeline Candidates Breakdown (if manifest has clips) */}
        {resultMeta?.manifest?.clips && resultMeta.manifest.clips.length > 0 && (
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                Selected Highlight Clips Breakdown
              </label>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDownloadManifest}
                className="text-xs text-slate-500 hover:text-[#FF5722]"
              >
                <FileCode className="w-3.5 h-3.5 mr-1" />
                View Full JSON Manifest
              </Button>
            </div>

            <div className="space-y-2">
              {resultMeta.manifest.clips.map((clip, index) => (
                <div
                  key={clip.clip_id || index}
                  className="flex items-center justify-between p-3.5 rounded-2xl bg-[#F6F8F6] border border-[#E7EBE7] text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-lg bg-orange-50 text-[#FF5722] border border-orange-200 flex items-center justify-center font-mono font-bold text-[11px]">
                      {index + 1}
                    </span>
                    <div>
                      <div className="font-bold text-slate-900 flex items-center gap-2">
                        <span>{clip.label || `Highlight Sequence #${index + 1}`}</span>
                        {clip.score && (
                          <span className="text-[10px] font-mono text-teal-800 bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                            Score: {clip.score.toFixed(2)}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                        Source: {clip.source_start_sec.toFixed(1)}s - {clip.source_end_sec.toFixed(1)}s
                      </div>
                    </div>
                  </div>

                  <div className="text-right font-mono">
                    <span className="font-bold text-[#FF5722]">
                      {clip.duration_sec.toFixed(1)}s
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500 border-t border-[#EEF2EE] py-3.5">
        <span className="font-mono text-[11px]">
          Job ID: {job.job_id}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleDownloadManifest}
            className="text-xs"
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>Download Manifest</span>
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleDownloadVideo}
            isLoading={downloading}
            className="text-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Finished Montage</span>
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
