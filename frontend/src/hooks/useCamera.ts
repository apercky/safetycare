"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CameraCreate, CameraUpdate } from "@/types";

export function useCameras() {
  return useQuery({
    queryKey: ["cameras"],
    queryFn: () => api.getCameras(),
    refetchInterval: 10000,
  });
}

export function useCamera(id: string) {
  return useQuery({
    queryKey: ["cameras", id],
    queryFn: () => api.getCamera(id),
    enabled: !!id,
  });
}

export function useCreateCamera() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CameraCreate) => api.createCamera(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
    },
  });
}

export function useUpdateCamera() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: CameraUpdate }) =>
      api.updateCamera(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      queryClient.invalidateQueries({ queryKey: ["cameras", id] });
    },
  });
}

export function useDeleteCamera() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteCamera(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
    },
  });
}

export function useStartCamera() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.startCamera(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      queryClient.invalidateQueries({ queryKey: ["cameras", id] });
    },
  });
}

export function useStopCamera() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.stopCamera(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      queryClient.invalidateQueries({ queryKey: ["cameras", id] });
    },
  });
}
