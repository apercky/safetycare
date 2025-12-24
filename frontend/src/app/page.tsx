"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import {
  Camera,
  Bell,
  Shield,
  LogOut,
  Plus,
  Activity,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useCameras } from "@/hooks/useCamera";
import { useAuthStore } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { VideoStream } from "@/components/VideoStream";
import { AlertBanner } from "@/components/AlertBanner";
import type { FallAlert, AlertPayload } from "@/types";

export default function DashboardPage() {
  const { isLoading } = useAuth();
  const { data: cameras, isLoading: camerasLoading } = useCameras();
  const logout = useAuthStore((s) => s.logout);
  const [alerts, setAlerts] = useState<FallAlert[]>([]);

  const handleAlert = useCallback((alert: AlertPayload, cameraId: string, cameraName: string) => {
    const fallAlert: FallAlert = {
      id: `${cameraId}-${Date.now()}-${alert.person_id}`,
      camera_id: cameraId,
      camera_name: cameraName,
      timestamp: new Date().toISOString(),
      confidence: alert.confidence,
      snapshot_url: alert.frame_snapshot ? `data:image/jpeg;base64,${alert.frame_snapshot}` : undefined,
      acknowledged: false,
    };
    setAlerts((prev) => [fallAlert, ...prev].slice(0, 5));
  }, []);

  const dismissAlert = useCallback((alertId: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
  }, []);

  if (isLoading || camerasLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Activity className="size-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const onlineCameras = cameras?.filter((c) => c.status === "streaming") || [];
  const totalCameras = cameras?.length || 0;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="size-6 text-primary" />
            <h1 className="text-xl font-bold">SafetyCare</h1>
          </div>

          <nav className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/cameras">
                <Camera className="mr-1 size-4" />
                Telecamere
              </Link>
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/settings/telegram">
                <Bell className="mr-1 size-4" />
                Notifiche
              </Link>
            </Button>
            <Button variant="ghost" size="icon" onClick={logout}>
              <LogOut className="size-4" />
            </Button>
          </nav>
        </div>
      </header>

      <main className="container py-6">
        {/* Alerts */}
        {alerts.length > 0 && (
          <div className="mb-6 space-y-2">
            {alerts.map((alert) => (
              <AlertBanner
                key={alert.id}
                alert={alert}
                onDismiss={() => dismissAlert(alert.id)}
              />
            ))}
          </div>
        )}

        {/* Stats */}
        <div className="mb-6 grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Telecamere Online
              </CardTitle>
              <Camera className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {onlineCameras.length}/{totalCameras}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Stato Sistema</CardTitle>
              <Activity className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Badge variant="success">Attivo</Badge>
                <span className="text-sm text-muted-foreground">
                  Monitoraggio in corso
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Alert Oggi</CardTitle>
              <Bell className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{alerts.length}</div>
            </CardContent>
          </Card>
        </div>

        {/* Camera Grid */}
        {onlineCameras.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {onlineCameras.map((camera) => (
              <Card key={camera.id} className="overflow-hidden">
                <VideoStream
                  cameraId={camera.id}
                  cameraName={camera.name}
                  className="aspect-video"
                  onAlert={handleAlert}
                />
              </Card>
            ))}
          </div>
        ) : (
          <Card className="py-12 text-center">
            <CardContent>
              <Camera className="mx-auto mb-4 size-12 text-muted-foreground" />
              <h3 className="mb-2 text-lg font-medium">
                Nessuna telecamera online
              </h3>
              <p className="mb-4 text-muted-foreground">
                Aggiungi o avvia una telecamera per iniziare il monitoraggio
              </p>
              <Button asChild>
                <Link href="/cameras">
                  <Plus className="mr-1 size-4" />
                  Gestisci Telecamere
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
