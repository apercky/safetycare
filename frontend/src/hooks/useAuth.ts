"use client";

import { useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/auth";

export function useAuth(options: { requireAuth?: boolean } = {}) {
  const { requireAuth = true } = options;
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading, needsSetup, checkAuth } = useAuthStore();
  const hasChecked = useRef(false);

  useEffect(() => {
    if (!hasChecked.current) {
      hasChecked.current = true;
      checkAuth();
    }
  }, [checkAuth]);

  useEffect(() => {
    // Don't redirect while still loading/checking auth
    if (isLoading) return;

    const isAuthPage = pathname === "/login" || pathname === "/setup";

    if (needsSetup && pathname !== "/setup") {
      router.replace("/setup");
      return;
    }

    if (requireAuth && !isAuthenticated && !needsSetup && !isAuthPage) {
      router.replace("/login");
      return;
    }

    if (isAuthenticated && isAuthPage) {
      router.replace("/");
      return;
    }
  }, [isAuthenticated, isLoading, needsSetup, pathname, requireAuth, router]);

  return {
    isAuthenticated,
    isLoading,
    needsSetup,
  };
}
