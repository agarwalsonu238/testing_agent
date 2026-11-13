import { BackendStatus } from "@/components/backend-status";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 p-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">testing_agent</h1>
        <p className="text-muted-foreground">Next.js frontend · FastAPI backend</p>
      </div>
      <BackendStatus />
    </main>
  );
}
