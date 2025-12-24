"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Plus, Camera, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { useCameras, useCreateCamera } from "@/hooks/useCamera";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CameraCard } from "@/components/CameraCard";
import type { CameraStream } from "@/types";

export default function CamerasPage() {
  const { isLoading: authLoading } = useAuth();
  const { data: cameras, isLoading: camerasLoading } = useCameras();
  const createCamera = useCreateCamera();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [stream, setStream] = useState<CameraStream>("stream2");
  const [port, setPort] = useState(554);

  const resetForm = () => {
    setName("");
    setIpAddress("");
    setUsername("");
    setPassword("");
    setStream("stream2");
    setPort(554);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createCamera.mutateAsync({
        name,
        ip_address: ipAddress,
        username,
        password,
        stream,
        port,
        enabled: true,
      });
      toast.success("Telecamera aggiunta con successo");
      setIsDialogOpen(false);
      resetForm();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Errore durante la creazione"
      );
    }
  };

  if (authLoading || camerasLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
        <div className="container flex h-16 items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <h1 className="text-xl font-bold">Gestione Telecamere</h1>

          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button className="ml-auto">
                <Plus className="mr-1 size-4" />
                Aggiungi
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <form onSubmit={handleCreate}>
                <DialogHeader>
                  <DialogTitle>Nuova Telecamera</DialogTitle>
                  <DialogDescription>
                    Inserisci i dati della telecamera Tapo C200
                  </DialogDescription>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Nome</Label>
                    <Input
                      id="name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="es. Soggiorno"
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="ip">Indirizzo IP</Label>
                    <Input
                      id="ip"
                      value={ipAddress}
                      onChange={(e) => setIpAddress(e.target.value)}
                      placeholder="192.168.1.100"
                      pattern="^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="username">Username</Label>
                      <Input
                        id="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="admin"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="password">Password</Label>
                      <Input
                        id="password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="stream">Qualità Stream</Label>
                      <Select
                        value={stream}
                        onValueChange={(value) => setStream(value as CameraStream)}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Seleziona qualità" />
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
                        onChange={(e) => setPort(parseInt(e.target.value) || 554)}
                        min={1}
                        max={65535}
                      />
                    </div>
                  </div>

                  <p className="text-xs text-muted-foreground">
                    Credenziali: App Tapo → Camera → Impostazioni → Avanzate → Account Camera
                  </p>
                </div>

                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsDialogOpen(false)}
                  >
                    Annulla
                  </Button>
                  <Button type="submit" disabled={createCamera.isPending}>
                    {createCamera.isPending ? (
                      <Loader2 className="mr-2 size-4 animate-spin" />
                    ) : null}
                    Aggiungi
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      <main className="container py-6">
        {cameras && cameras.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {cameras.map((camera) => (
              <CameraCard key={camera.id} camera={camera} />
            ))}
          </div>
        ) : (
          <Card className="py-12 text-center">
            <CardContent>
              <Camera className="mx-auto mb-4 size-12 text-muted-foreground" />
              <h3 className="mb-2 text-lg font-medium">
                Nessuna telecamera configurata
              </h3>
              <p className="mb-4 text-muted-foreground">
                Aggiungi la tua prima telecamera per iniziare il monitoraggio
              </p>
              <Button onClick={() => setIsDialogOpen(true)}>
                <Plus className="mr-1 size-4" />
                Aggiungi Telecamera
              </Button>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
