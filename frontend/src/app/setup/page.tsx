"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, AlertTriangle, Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { PasswordDisplay } from "@/components/PasswordDisplay";

export default function SetupPage() {
  useAuth({ requireAuth: false });
  const router = useRouter();
  const { setup, acknowledgeSetup, isLoading, error } = useAuthStore();

  const [password, setPassword] = useState<string | null>(null);
  const [isSettingUp, setIsSettingUp] = useState(false);

  const handleSetup = async () => {
    setIsSettingUp(true);
    const generatedPassword = await setup();
    if (generatedPassword) {
      setPassword(generatedPassword);
    }
    setIsSettingUp(false);
  };

  const handleContinue = async () => {
    await acknowledgeSetup();
    router.replace("/login");
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-primary/10">
            <Shield className="size-8 text-primary" />
          </div>
          <CardTitle className="text-2xl">Configurazione Iniziale</CardTitle>
          <CardDescription>
            {password
              ? "Salva questa password in un luogo sicuro"
              : "Benvenuto in SafetyCare! Configura il sistema per iniziare."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {password ? (
            <>
              <Alert variant="warning" className="border-warning bg-warning/10">
                <AlertTriangle className="size-4" />
                <AlertTitle>Importante!</AlertTitle>
                <AlertDescription>
                  Questa password verrà mostrata solo una volta. Salvala in un
                  luogo sicuro prima di continuare.
                </AlertDescription>
              </Alert>

              <div>
                <p className="mb-2 text-sm font-medium">La tua password:</p>
                <PasswordDisplay password={password} />
              </div>

              <Button onClick={handleContinue} className="w-full">
                Ho salvato la password, continua
              </Button>
            </>
          ) : (
            <>
              <p className="text-muted-foreground">
                Cliccando il pulsante qui sotto, verrà generata una password
                sicura per accedere al sistema SafetyCare. Questa password sarà
                l&apos;unico modo per accedere al pannello di controllo.
              </p>

              <Button
                onClick={handleSetup}
                className="w-full"
                disabled={isSettingUp}
              >
                {isSettingUp ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    Generazione in corso...
                  </>
                ) : (
                  "Genera Password e Configura"
                )}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
