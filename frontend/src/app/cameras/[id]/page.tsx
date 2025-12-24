import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { CameraDetail } from "./CameraDetail";

interface PageProps {
  params: Promise<{ id: string }>;
}

function Loading() {
  return (
    <div className="flex h-screen items-center justify-center">
      <Loader2 className="size-8 animate-spin text-muted-foreground" />
    </div>
  );
}

export default async function CameraDetailPage({ params }: PageProps) {
  const { id } = await params;

  return (
    <Suspense fallback={<Loading />}>
      <CameraDetail id={id} />
    </Suspense>
  );
}
