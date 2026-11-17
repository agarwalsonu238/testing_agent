import Link from "next/link";

export default function NotFound() {
  return (
    <div className="grid gap-2">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link href="/" className="underline underline-offset-4">
        Go to To review
      </Link>
    </div>
  );
}
