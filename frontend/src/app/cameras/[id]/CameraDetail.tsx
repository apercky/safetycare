"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Play, Square, Save, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import {
  useCamera,
  useUpdateCamera,
  useStartCamera,
  useStopCamera,
} from "@/hooks/useCamera";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { VideoStream } from "@/components/VideoStream";
import { formatDate } from "@/lib/utils";
import type { CameraStream, CameraStatus } from "@/types";

interface CameraDetailProps {
  id: string;
}

export function CameraDetail({ id }: CameraDetailProps) {
  const { isLoading: authLoading } = useAuth();
  const { data: camera, isLoading: cameraLoading } = useCamera(id);
  const updateCamera = useUpdateCamera();
  const startCamera = useStartCamera();
  const stopCamera = useStopCamera();

  const [name, setName] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [stream, setStream] = useState<CameraStream>("stream2");
  const [port, setPort] = useState(554);
  const [enabled, setEnabled] = useState(true);
  const [hasChanges, setHasChanges] = useState(false);

  // Initialize form when camera loads
  useEffect(() => {
    if (camera && !hasChanges) {
      setName(camera.name);
      setIpAddress(camera.ip_address);
      setUsername(camera.username);
      setStream(camera.stream);
      setPort(camera.port);
      setEnabled(camera.enabled);
    }
  }, [camera, hasChanges]);

  const handleSave = async () => {
    try {
      await updateCamera.mutateAsync({
        id,
        data: {
          name,
          ip_address: ipAddress,
          username,
          ...(password && { password }),
          stream,
          port,
          enabled,
        },
      });
      toast.success("Telecamera aggiornata");
      setHasChanges(false);
      setPassword("");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Errore durante il salvataggio"
      );
    }
  };

  const handleStart = async () => {
    try {
      await startCamera.mutateAsync(id);
      toast.success("Streaming avviato");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore avvio streaming");
    }
  };

  const handleStop = async () => {
    try {
      await stopCamera.mutateAsync(id);
      toast.success("Streaming fermato");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore stop streaming");
    }
  };

  if (authLoading || cameraLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!camera) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-muted-foreground">Telecamera non trovata</p>
      </div>
    );
  }

  const statusVariant: Record<CameraStatus, "default" | "secondary" | "destructive" | "outline"> = {
    streaming: "default",
    connecting: "secondary",
    idle: "outline",
    disabled: "secondary",
    error: "destructive",
  };

  const isStreaming = camera.status === "streaming";

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
        <div className="container flex h-16 items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/cameras">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <h1 className="text-xl font-bold">{camera.name}</h1>
          <Badge variant={statusVariant[camera.status]}>{camera.status}</Badge>

          <div className="ml-auto flex items-center gap-2">
            {isStreaming ? (
              <Button
                variant="outline"
                onClick={handleStop}
                disabled={stopCamera.isPending}
              >
                <Square className="mr-1 size-4" />
                Stop
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={handleStart}
                disabled={startCamera.isPending || camera.status === "disabled"}
              >
                <Play className="mr-1 size-4" />
                Start
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="container py-6">
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Video Stream */}
          <Card className="overflow-hidden lg:col-span-2">
            <CardHeader>
              <CardTitle>Live Stream</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {isStreaming ? (
                <VideoStream
                  cameraId={camera.id}
                  className="aspect-video w-full"
                />
              ) : (
                <div className="flex aspect-video items-center justify-center bg-muted">
                  <p className="text-muted-foreground">
                    {camera.status === "disabled"
                      ? "Telecamera disabilitata"
                      : "Avvia lo streaming per visualizzare il video"}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Settings */}
          <Card>
            <CardHeader>
              <CardTitle>Impostazioni</CardTitle>
              <CardDescription>
                Modifica le impostazioni della telecamera
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Nome</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    setHasChanges(true);
                  }}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="ip">Indirizzo IP</Label>
                <Input
                  id="ip"
                  value={ipAddress}
                  onChange={(e) => {
                    setIpAddress(e.target.value);
                    setHasChanges(true);
                  }}
                  placeholder="192.168.1.100"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      setHasChanges(true);
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Nuova Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setHasChanges(true);
                    }}
                    placeholder="Lascia vuoto per non cambiare"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="stream">Qualità Stream</Label>
                  <Select
                    value={stream}
                    onValueChange={(value) => {
                      setStream(value as CameraStream);
                      setHasChanges(true);
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="stream2">720p (Raccomandato)</SelectItem>
                      <SelectItem value="stream1">1080p</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="port">Porta RTSP</Label>
                  <Input
                    id="port"
                    type="number"
                    value={port}
                    onChange={(e) => {
                      setPort(parseInt(e.target.value) || 554);
                      setHasChanges(true);
                    }}
                    min={1}
                    max={65535}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="enabled">Abilitata</Label>
                <Switch
                  id="enabled"
                  checked={enabled}
                  onCheckedChange={(checked) => {
                    setEnabled(checked);
                    setHasChanges(true);
                  }}
                />
              </div>

              <Button
                onClick={handleSave}
                disabled={!hasChanges || updateCamera.isPending}
                className="w-full"
              >
                {updateCamera.isPending ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Save className="mr-1 size-4" />
                )}
                Salva Modifiche
              </Button>
            </CardContent>
          </Card>

          {/* Info */}
          <Card>
            <CardHeader>
              <CardTitle>Informazioni</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">ID</span>
                <code className="text-sm">{camera.id}</code>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Indirizzo</span>
                <span>{camera.ip_address}:{camera.port}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Creata</span>
                <span>{formatDate(camera.created_at)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Aggiornata</span>
                <span>{formatDate(camera.updated_at)}</span>
              </div>
              {camera.last_seen && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Ultima connessione</span>
                  <span>{formatDate(camera.last_seen)}</span>
                </div>
              )}
              {camera.error_message && (
                <div className="mt-4 rounded-md bg-destructive/10 p-3">
                  <p className="text-sm text-destructive">{camera.error_message}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
