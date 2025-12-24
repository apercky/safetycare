"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import type { FallAlert } from "@/types";

interface AlertBannerProps {
  alert: FallAlert;
  onDismiss?: () => void;
  autoDismissMs?: number;
}

export function AlertBanner({
  alert,
  onDismiss,
  autoDismissMs = 30000,
}: AlertBannerProps) {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (autoDismissMs > 0) {
      const timer = setTimeout(() => {
        setIsVisible(false);
        onDismiss?.();
      }, autoDismissMs);
      return () => clearTimeout(timer);
    }
  }, [autoDismissMs, onDismiss]);

  if (!isVisible) return null;

  return (
    <Alert
      variant="destructive"
      className="animate-pulse-alert border-destructive bg-destructive/10"
    >
      <AlertTriangle className="size-5" />
      <div className="flex flex-1 items-start justify-between">
        <div>
          <AlertTitle className="text-lg font-semibold">
            ⚠️ Caduta Rilevata!
          </AlertTitle>
          <AlertDescription className="mt-1">
            <p>
              <strong>{alert.camera_name}</strong> -{" "}
              {formatDate(alert.timestamp)}
            </p>
            <p className="text-sm">
              Confidenza: {Math.round(alert.confidence * 100)}%
            </p>
          </AlertDescription>
        </div>

        {alert.snapshot_url && (
          <img
            src={alert.snapshot_url}
            alt="Snapshot"
            className="ml-4 h-20 w-auto rounded border"
          />
        )}

        <Button
          size="icon"
          variant="ghost"
          className="ml-2 shrink-0"
          onClick={() => {
            setIsVisible(false);
            onDismiss?.();
          }}
        >
          <X className="size-4" />
        </Button>
      </div>
    </Alert>
  );
}
