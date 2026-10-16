import Link from "next/link";
import { SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="container flex min-h-[60vh] items-center justify-center py-16">
      <div className="max-w-md text-center">
        <SearchX className="mx-auto size-10 text-muted-foreground" />
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">We couldn&rsquo;t find that</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          The offer may have expired and been archived, or the page may have moved. Try the
          directory — expired offers live in their own section.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button asChild>
            <Link href="/offers">Browse offers</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/expired">Recently expired</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}