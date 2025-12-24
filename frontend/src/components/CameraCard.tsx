"use client";

import Link from "next/link";
import { useState } from "react";
import { Camera as CameraIcon, Play, Square, Trash2, Settings } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useStartCamera, useStopCamera, useDeleteCamera } from "@/hooks/useCamera";
import { cn, formatDate } from "@/lib/utils";
import type { Camera, CameraStatus } from "@/types";

interface CameraCardProps {
  camera: Camera;
}

export function CameraCard({ camera }: CameraCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const startCamera = useStartCamera();
  const stopCamera = useStopCamera();
  const deleteCamera = useDeleteCamera();

  const handleStart = () => startCamera.mutate(camera.id);
  const handleStop = () => stopCamera.mutate(camera.id);
  const handleDelete = async () => {
    setIsDeleting(true);
    await deleteCamera.mutateAsync(camera.id);
  };

  const statusVariant: Record<CameraStatus, "default" | "secondary" | "destructive" | "outline" | "success"> = {
    streaming: "success",
    connecting: "secondary",
    idle: "outline",
    disabled: "secondary",
    error: "destructive",
  };

  const isStreaming = camera.status === "streaming";
  const isDisabled = camera.status === "disabled";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <CameraIcon className="size-4" />
          {camera.name}
        </CardTitle>
        <Badge variant={statusVariant[camera.status]}>{camera.status}</Badge>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <p className="truncate text-sm text-muted-foreground">
            {camera.ip_address}:{camera.port}
          </p>

          {camera.last_seen && (
            <p className="text-xs text-muted-foreground">
              Ultima connessione: {formatDate(camera.last_seen)}
            </p>
          )}

          {camera.error_message && (
            <p className="text-xs text-destructive">
              {camera.error_message}
            </p>
          )}

          <div className="flex items-center gap-2">
            {isStreaming ? (
              <Button
                size="sm"
                variant="outline"
                onClick={handleStop}
                disabled={stopCamera.isPending}
              >
                <Square className="mr-1 size-3" />
                Stop
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={handleStart}
                disabled={startCamera.isPending || camera.status === "connecting" || isDisabled}
              >
                <Play className="mr-1 size-3" />
                Start
              </Button>
            )}

            <Button size="sm" variant="outline" asChild>
              <Link href={`/cameras/${camera.id}`}>
                <Settings className="mr-1 size-3" />
                Dettagli
              </Link>
            </Button>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className={cn(
                    "ml-auto text-destructive hover:bg-destructive/10 hover:text-destructive"
                  )}
                  disabled={isDeleting}
                >
                  <Trash2 className="size-4" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Elimina telecamera</AlertDialogTitle>
                  <AlertDialogDescription>
                    Sei sicuro di voler eliminare &quot;{camera.name}&quot;? Questa
                    azione non può essere annullata.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Annulla</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDelete}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Elimina
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
