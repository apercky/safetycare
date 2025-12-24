"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Wifi, WifiOff, Loader2, RefreshCw } from "lucide-react";
import type { DetectionPayload, AlertPayload, PersonDetectionResult } from "@/types";

interface VideoStreamProps {
  cameraId: string;
  cameraName?: string;
  className?: string;
  showOverlay?: boolean;
  onAlert?: (alert: AlertPayload, cameraId: string, cameraName: string) => void;
}

export function VideoStream({
  cameraId,
  cameraName,
  className,
  showOverlay = true,
  onAlert,
}: VideoStreamProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [detection, setDetection] = useState<DetectionPayload | null>(null);

  const handleAlert = useCallback((alert: AlertPayload) => {
    onAlert?.(alert, cameraId, cameraName || "Camera");
  }, [onAlert, cameraId, cameraName]);

  const { status, lastFrame, isConnected, retry } = useWebSocket(cameraId, {
    onDetection: setDetection,
    onAlert: handleAlert,
  });

  useEffect(() => {
    if (!lastFrame || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);

      // Draw overlay for each detected person
      if (showOverlay && detection?.persons) {
        detection.persons.forEach((person) => {
          drawPersonOverlay(ctx, person, canvas.width, canvas.height);
        });
      }
    };
    img.src = `data:image/jpeg;base64,${lastFrame}`;
  }, [lastFrame, detection, showOverlay]);

  return (
    <div className={cn("relative overflow-hidden rounded-lg bg-black", className)}>
      <canvas
        ref={canvasRef}
        className="size-full object-contain"
      />

      {/* Status overlay */}
      <div className="absolute right-2 top-2">
        <Badge
          variant={isConnected ? "success" : status === "max_retries" ? "destructive" : "secondary"}
          className="gap-1"
        >
          {status === "connecting" ? (
            <Loader2 className="size-3 animate-spin" />
          ) : isConnected ? (
            <Wifi className="size-3" />
          ) : (
            <WifiOff className="size-3" />
          )}
          {status === "max_retries" ? "offline" : status}
        </Badge>
      </div>

      {/* Camera name */}
      {cameraName && (
        <div className="absolute bottom-2 left-2">
          <Badge variant="secondary">{cameraName}</Badge>
        </div>
      )}

      {/* Fall alert indicator */}
      {detection?.fall_detected && (
        <div className="absolute inset-0 animate-pulse border-4 border-destructive" />
      )}

      {/* Loading state */}
      {!lastFrame && status === "connecting" && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Max retries state */}
      {status === "max_retries" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80">
          <WifiOff className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Connessione fallita</p>
          <Button size="sm" variant="secondary" onClick={retry}>
            <RefreshCw className="mr-1 size-3" />
            Riprova
          </Button>
        </div>
      )}
    </div>
  );
}

function drawPersonOverlay(
  ctx: CanvasRenderingContext2D,
  person: PersonDetectionResult,
  width: number,
  height: number
) {
  const { bbox, pose_landmarks, state, confidence } = person;
  const isFalling = state === "falling";

  // Bounding box color based on state
  const boxColor = isFalling ? "#ef4444" : state === "lying" ? "#f97316" : "#22c55e";
  ctx.strokeStyle = boxColor;
  ctx.lineWidth = isFalling ? 3 : 2;
  ctx.strokeRect(
    bbox.x * width,
    bbox.y * height,
    bbox.width * width,
    bbox.height * height
  );

  // Label
  ctx.fillStyle = boxColor;
  ctx.font = "14px sans-serif";
  const label = `${state} (${Math.round(confidence * 100)}%)`;
  const labelWidth = ctx.measureText(label).width + 8;
  ctx.fillRect(
    bbox.x * width,
    bbox.y * height - 20,
    labelWidth,
    20
  );
  ctx.fillStyle = "#ffffff";
  ctx.fillText(
    label,
    bbox.x * width + 4,
    bbox.y * height - 5
  );

  // Pose skeleton
  if (pose_landmarks && pose_landmarks.length > 0) {
    const connections = [
      [11, 12], // shoulders
      [11, 13], [13, 15], // left arm
      [12, 14], [14, 16], // right arm
      [11, 23], [12, 24], // torso
      [23, 24], // hips
      [23, 25], [25, 27], // left leg
      [24, 26], [26, 28], // right leg
    ];

    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 2;

    connections.forEach(([i, j]) => {
      const p1 = pose_landmarks[i];
      const p2 = pose_landmarks[j];
      if (p1 && p2 && p1.visibility > 0.5 && p2.visibility > 0.5) {
        ctx.beginPath();
        ctx.moveTo(p1.x * width, p1.y * height);
        ctx.lineTo(p2.x * width, p2.y * height);
        ctx.stroke();
      }
    });

    // Draw joints
    ctx.fillStyle = "#60a5fa";
    pose_landmarks.forEach((landmark) => {
      if (landmark.visibility > 0.5) {
        ctx.beginPath();
        ctx.arc(landmark.x * width, landmark.y * height, 4, 0, 2 * Math.PI);
        ctx.fill();
      }
    });
  }
}
