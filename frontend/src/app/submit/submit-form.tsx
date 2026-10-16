"use client";

import * as React from "react";
import Link from "next/link";
import { Check, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { Category } from "@/lib/types";

const OFFER_TYPES = [
  { value: "free_trial", label: "Free trial" },
  { value: "free", label: "Genuinely free" },
  { value: "freemium", label: "Freemium plan" },
  { value: "free_credits", label: "Free credits" },
  { value: "discount", label: "Discount" },
  { value: "coupon", label: "Coupon code" },
  { value: "cashback", label: "Cashback" },
  { value: "free_alternative", label: "Free alternative" },
];

export function SubmitForm({ categories }: { categories: Category[] }) {
  const { toast } = useToast();
  const [title, setTitle] = React.useState("");
  const [url, setUrl] = React.useState("");
  const [brand, setBrand] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [offerType, setOfferType] = React.useState("free_trial");
  const [notes, setNotes] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [done, setDone] = React.useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await api.submitOffer({
        title,
        url,
        brand_name: brand || undefined,
        category_slug: category || undefined,
        offer_type: offerType,
        notes: notes || undefined,
      });
      setDone(true);
      toast({
        title: "Thanks — submitted for review",
        description: "A reviewer confirms every offer against its official page before it goes live.",
        tone: "success",
      });
    } catch (error) {
      toast({
        title: "Could not submit",
        description: error instanceof Error ? error.message : "Please try again.",
        tone: "error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="rounded-2xl border border-success/40 bg-success/10 p-8 text-center">
        <Check className="mx-auto size-8 text-success" />
        <h2 className="mt-3 text-lg font-semibold">Submission received</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
          Nothing is published automatically. We open the official page, check that the terms match
          what you described, and only then add it to the directory.
        </p>
        <div className="mt-5 flex justify-center gap-2">
          <Button asChild>
            <Link href="/offers">Browse offers</Link>
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setDone(false);
              setTitle("");
              setUrl("");
              setBrand("");
              setNotes("");
            }}
          >
            Submit another
          </Button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-card/50 p-6">
      <div>
        <Label htmlFor="title">Offer title</Label>
        <Input
          id="title"
          required
          minLength={6}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="e.g. Three months of the Pro plan free for new accounts"
          className="mt-1.5"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="url">Official page URL</Label>
          <Input
            id="url"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com/pricing"
            className="mt-1.5"
          />
        </div>
        <div>
          <Label htmlFor="brand">Brand</Label>
          <Input
            id="brand"
            value={brand}
            onChange={(event) => setBrand(event.target.value)}
            placeholder="Example Inc"
            className="mt-1.5"
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="category">Category</Label>
          <select
            id="category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="mt-1.5 flex h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm outline-none"
          >
            <option value="">Not sure</option>
            {categories.map((item) => (
              <option key={item.slug} value={item.slug}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label htmlFor="offer_type">Offer type</Label>
          <select
            id="offer_type"
            value={offerType}
            onChange={(event) => setOfferType(event.target.value)}
            className="mt-1.5 flex h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm outline-none"
          >
            {OFFER_TYPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <Label htmlFor="notes">Details for the reviewer</Label>
        <Textarea
          id="notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="What exactly is free, for how long, and what are the eligibility rules? Link to the terms page if there is one."
          className="mt-1.5"
        />
      </div>

      <Button type="submit" disabled={submitting}>
        <Send className="size-4" />
        {submitting ? "Submitting…" : "Submit for review"}
      </Button>
    </form>
  );
}