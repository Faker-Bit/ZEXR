import { OfferCardSkeleton } from "@/components/offers/offer-card";

export default function Loading() {
  return (
    <div className="container py-10">
      <div className="skeleton mb-4 h-9 w-72 rounded-lg" />
      <div className="skeleton mb-8 h-4 w-96 max-w-full rounded" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <OfferCardSkeleton key={index} />
        ))}
      </div>
    </div>
  );
}