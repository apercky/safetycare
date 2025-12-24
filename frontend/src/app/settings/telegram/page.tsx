"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Save, Send, Loader2, MessageCircle } from "lucide-react";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function TelegramSettingsPage() {
  const { isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const { data: config, isLoading: configLoading } = useQuery({
    queryKey: ["telegram-config"],
    queryFn: () => api.getTelegramConfig(),
  });

  const updateConfig = useMutation({
    mutationFn: api.configureTelegram.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telegram-config"] });
    },
  });

  const testTelegram = useMutation({
    mutationFn: () => api.testTelegram(),
  });

  const [enabled, setEnabled] = useState(false);
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [cooldown, setCooldown] = useState(30);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (config) {
      setEnabled(config.enabled);
      // bot_token e chat_id non sono nella risposta GET (per sicurezza)
      // Impostiamo solo i valori mascherati/defaults
      setCooldown(config.alert_cooldown_seconds);
    }
  }, [config]);

  const handleChange = () => {
    setHasChanges(true);
  };

  const handleSave = async () => {
    try {
      await updateConfig.mutateAsync({
        bot_token: botToken,
        chat_id: chatId,
        enabled,
        alert_cooldown_seconds: cooldown,
      });
      toast.success("Configurazione salvata");
      setHasChanges(false);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Errore durante il salvataggio"
      );
    }
  };

  const handleTest = async () => {
    try {
      const result = await testTelegram.mutateAsync();
      if (result.success) {
        toast.success("Messaggio di test inviato!");
      } else {
        toast.error(result.message);
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Errore durante il test"
      );
    }
  };

  if (authLoading || configLoading) {
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
          <h1 className="text-xl font-bold">Notifiche Telegram</h1>
        </div>
      </header>

      <main className="container max-w-2xl py-6">
        <div className="space-y-6">
          {/* Instructions */}
          <Alert>
            <MessageCircle className="size-4" />
            <AlertTitle>Come configurare Telegram</AlertTitle>
            <AlertDescription className="mt-2 space-y-2">
              <ol className="list-inside list-decimal space-y-1 text-sm">
                <li>
                  Crea un bot su Telegram parlando con{" "}
                  <a
                    href="https://t.me/BotFather"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium underline"
                  >
                    @BotFather
                  </a>
                </li>
                <li>Copia il token del bot che ricevi</li>
                <li>
                  Avvia una chat con il tuo bot e ottieni il chat ID da{" "}
                  <a
                    href="https://t.me/userinfobot"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium underline"
                  >
                    @userinfobot
                  </a>
                </li>
                <li>Inserisci i dati qui sotto e salva</li>
              </ol>
            </AlertDescription>
          </Alert>

          {/* Configuration */}
          <Card>
            <CardHeader>
              <CardTitle>Configurazione</CardTitle>
              <CardDescription>
                Configura le notifiche Telegram per ricevere alert in caso di
                caduta
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="enabled">Notifiche abilitate</Label>
                  <p className="text-sm text-muted-foreground">
                    Ricevi notifiche su Telegram quando viene rilevata una caduta
                  </p>
                </div>
                <Switch
                  id="enabled"
                  checked={enabled}
                  onCheckedChange={(checked) => {
                    setEnabled(checked);
                    handleChange();
                  }}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="token">Bot Token</Label>
                <Input
                  id="token"
                  type="password"
                  value={botToken}
                  onChange={(e) => {
                    setBotToken(e.target.value);
                    handleChange();
                  }}
                  placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="chatId">Chat ID</Label>
                <Input
                  id="chatId"
                  value={chatId}
                  onChange={(e) => {
                    setChatId(e.target.value);
                    handleChange();
                  }}
                  placeholder={config?.chat_id_masked || "123456789"}
                />
                {config?.configured && config?.chat_id_masked && !chatId && (
                  <p className="text-xs text-muted-foreground">
                    Configurato: {config.chat_id_masked}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="cooldown">Cooldown (secondi)</Label>
                <Input
                  id="cooldown"
                  type="number"
                  min={10}
                  max={300}
                  value={cooldown}
                  onChange={(e) => {
                    setCooldown(parseInt(e.target.value) || 30);
                    handleChange();
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  Tempo minimo tra una notifica e l&apos;altra (10-300 secondi)
                </p>
              </div>

              <div className="flex gap-2 pt-4">
                <Button
                  onClick={handleSave}
                  disabled={!hasChanges || updateConfig.isPending}
                  className="flex-1"
                >
                  {updateConfig.isPending ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Save className="mr-1 size-4" />
                  )}
                  Salva
                </Button>
                <Button
                  variant="outline"
                  onClick={handleTest}
                  disabled={!enabled || !botToken || !chatId || testTelegram.isPending}
                >
                  {testTelegram.isPending ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Send className="mr-1 size-4" />
                  )}
                  Test
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
