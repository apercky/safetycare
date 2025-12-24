"use client";

import { useState } from "react";
import { Eye, EyeOff, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PasswordDisplayProps {
  password: string;
  className?: string;
}

export function PasswordDisplay({ password, className }: PasswordDisplayProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(password);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border bg-muted p-3",
        className
      )}
    >
      <code className="flex-1 font-mono text-lg">
        {isVisible ? password : "•".repeat(password.length)}
      </code>

      <Button
        size="icon"
        variant="ghost"
        onClick={() => setIsVisible(!isVisible)}
        aria-label={isVisible ? "Nascondi password" : "Mostra password"}
      >
        {isVisible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </Button>

      <Button
        size="icon"
        variant="ghost"
        onClick={handleCopy}
        aria-label="Copia password"
      >
        {isCopied ? (
          <Check className="size-4 text-success" />
        ) : (
          <Copy className="size-4" />
        )}
      </Button>
    </div>
  );
}
