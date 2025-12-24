"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { WebSocketManager } from "@/lib/websocket";
import { api } from "@/lib/api";
import type {
  WebSocketMessage,
  FrameMessage,
  DetectionMessage,
  AlertMessage,
  DetectionPayload,
  AlertPayload,
} from "@/types";

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error" | "max_retries";

interface UseWebSocketOptions {
  onFrame?: (frame: string) => void;
  onDetection?: (detection: DetectionPayload) => void;
  onAlert?: (alert: AlertPayload) => void;
  autoConnect?: boolean;
}

export function useWebSocket(cameraId: string, options: UseWebSocketOptions = {}) {
  const { onFrame, onDetection, onAlert, autoConnect = true } = options;

  const wsRef = useRef<WebSocketManager | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [lastFrame, setLastFrame] = useState<string | null>(null);
  const [lastDetection, setLastDetection] = useState<DetectionPayload | null>(null);

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.type) {
        case "frame": {
          const frameMsg = message as FrameMessage;
          const frameData = frameMsg.payload.frame;
          setLastFrame(frameData);
          onFrame?.(frameData);
          break;
        }
        case "detection": {
          const detectionMsg = message as DetectionMessage;
          setLastDetection(detectionMsg.payload);
          onDetection?.(detectionMsg.payload);
          break;
        }
        case "alert": {
          const alertMsg = message as AlertMessage;
          onAlert?.(alertMsg.payload);
          break;
        }
      }
    },
    [onFrame, onDetection, onAlert]
  );

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.disconnect();
    }

    const url = api.getWebSocketUrl(cameraId);
    wsRef.current = new WebSocketManager(url);

    wsRef.current.onStatus(setStatus);
    wsRef.current.onMessage(handleMessage);
    wsRef.current.connect();
  }, [cameraId, handleMessage]);

  const retry = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.resetReconnectAttempts();
      wsRef.current.connect();
    } else {
      connect();
    }
  }, [connect]);

  const disconnect = useCallback(() => {
    wsRef.current?.disconnect();
    wsRef.current = null;
    setStatus("disconnected");
  }, []);

  useEffect(() => {
    if (autoConnect && cameraId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, cameraId, connect, disconnect]);

  return {
    status,
    lastFrame,
    lastDetection,
    connect,
    disconnect,
    retry,
    isConnected: status === "connected",
  };
}
