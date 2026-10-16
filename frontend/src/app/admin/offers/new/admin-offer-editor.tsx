"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Save } from "lucide-react";
import { AdminShell } from "@/components/admin/shell";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { Category, OfferType } from "@/lib/types";

const TYPES: OfferType[] = [
  "free", "free_trial", "freemium", "free_credits", "discount", "coupon", "cashback", "free_alternative",
];

export function AdminOfferEditor({ categories }: { categories: Category[] }) {
  const router = useRouter();
  const { toast } = useToast();
  const [form, setForm] = React.useState({
    title: "",
    short_description: "",
    description: "",
    category_id: categories[0]?.id ?? "",
    offer_type: "free_trial" as OfferType,
    currency: "USD",
    original_price: "",
    promo_price: "",
    trial_days: "",
    credits_amount: "",
    credits_unit: "credit",
    billing_period: "monthly",
    official_url: "",
    coupon_code: "",
    expires_at: "",
    how_to_redeem: "",
    is_genuinely_free: false,
    requires_payment_method: false,
    requires_student_id: false,
  });
  const [submitting, setSubmitting] = React.useState(false);

  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }));

  async function submit(event: React.FormEvent, publish: boolean) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        title: form.title,
        short_description: form.short_description,
        description: form.description,
        category_id: form.category_id,
        offer_type: form.offer_type,
        currency: form.currency.toUpperCase(),
        official_url: form.official_url,
        coupon_code: form.coupon_code || undefined,
        trial_days: form.trial_days ? Number(form.trial_days) : null,
        credits_amount: form.credits_amount ? Number(form.credits_amount) : null,
        credits_unit: form.credits_unit || null,
        billing_period: form.billing_period || null,
        original_price: form.original_price ? Number(form.original_price) : null,
        promo_price: form.promo_price ? Number(form.promo_price) : null,
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
        how_to_redeem: form.how_to_redeem
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
        is_genuinely_free: form.is_genuinely_free,
        requires_payment_method: form.requires_payment_method,
        requires_student_id: form.requires_student_id,
        status: "pending_review",
        verification_status: "unverified",
      };
      const created = await api.createOffer(payload);
      if (publish) {
        await api.changeOfferStatus(created.id, { status: "published" });
      }
      toast({
        title: publish ? "Offer created and published" : "Draft created",
        description: "Verification runs on the next sweep.",
        tone: "success",
      });
      router.push("/admin/offers");
    } catch (error) {
      toast({
        title: "Could not save the offer",
        tone: "error",
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AdminShell
      title="New offer"
      description="Manually entered offers start as pending_review and unverified — publish only after checking the official page."
    >
      <form
        onSubmit={(event) => submit(event, false)}
        className="max-w-3xl space-y-5 rounded-2xl border border-border bg-card/50 p-6"
      >
        <div>
          <Label htmlFor="title">Title</Label>
          <Input
            id="title"
            required
            minLength={4}
            value={form.title}
            onChange={(event) => set({ title: event.target.value })}
            className="mt-1.5"
          />
        </div>

        <div>
          <Label htmlFor="short_description">Short description (shown on cards)</Label>
          <Input
            id="short_description"
            required
            minLength={10}
            value={form.short_description}
            onChange={(event) => set({ short_description: event.target.value })}
            className="mt-1.5"
          />
        </div>

        <div>
          <Label htmlFor="description">Full description</Label>
          <Textarea
            id="description"
            required
            minLength={20}
            value={form.description}
            onChange={(event) => set({ description: event.target.value })}
            className="mt-1.5 min-h-[140px]"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <Label htmlFor="category_id">Category</Label>
            <Select
              id="category_id"
              required
              value={form.category_id}
              onChange={(event) => set({ category_id: event.target.value })}
              className="mt-1.5"
            >
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="offer_type">Offer type</Label>
            <Select
              id="offer_type"
              value={form.offer_type}
              onChange={(event) => set({ offer_type: event.target.value as OfferType })}
              className="mt-1.5"
            >
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {type.replace("_", " ")}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="currency">Currency</Label>
            <Input
              id="currency"
              value={form.currency}
              maxLength={3}
              onChange={(event) => set({ currency: event.target.value.toUpperCase() })}
              className="mt-1.5"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-4">
          <div>
            <Label htmlFor="original_price">Original price</Label>
            <Input
              id="original_price"
              type="number"
              step="0.01"
              min={0}
              value={form.original_price}
              onChange={(event) => set({ original_price: event.target.value })}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor="promo_price">Promo price</Label>
            <Input
              id="promo_price"
              type="number"
              step="0.01"
              min={0}
              value={form.promo_price}
              onChange={(event) => set({ promo_price: event.target.value })}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor="trial_days">Trial days</Label>
            <Input
              id="trial_days"
              type="number"
              min={0}
              value={form.trial_days}
              onChange={(event) => set({ trial_days: event.target.value })}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor="billing_period">Billing period</Label>
            <Select
              id="billing_period"
              value={form.billing_period}
              onChange={(event) => set({ billing_period: event.target.value })}
              className="mt-1.5"
            >
              <option value="">—</option>
              <option value="monthly">monthly</option>
              <option value="yearly">yearly</option>
              <option value="lifetime">lifetime</option>
              <option value="one-time">one-time</option>
            </Select>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <Label htmlFor="credits_amount">Credits amount</Label>
            <Input
              id="credits_amount"
              type="number"
              step="0.01"
              min={0}
              value={form.credits_amount}
              onChange={(event) => set({ credits_amount: event.target.value })}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor="credits_unit">Credits unit</Label>
            <Input
              id="credits_unit"
              value={form.credits_unit}
              onChange={(event) => set({ credits_unit: event.target.value })}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor="expires_at">Expires at</Label>
            <Input
              id="expires_at"
              type="datetime-local"
              value={form.expires_at}
              onChange={(event) => set({ expires_at: event.target.value })}
              className="mt-1.5"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="official_url">Official page URL</Label>
            <Input
              id="official_url"
              required
              value={form.official_url}
              onChange={(event) => set({ official_url: event.target.value })}
              placeholder="https://provider.com/pricing"
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor="coupon_code">Coupon code</Label>
            <Input
              id="coupon_code"
              value={form.coupon_code}
              onChange={(event) => set({ coupon_code: event.target.value.toUpperCase() })}
              className="mt-1.5"
            />
          </div>
        </div>

        <div>
          <Label htmlFor="how_to_redeem">Redemption steps (one per line)</Label>
          <Textarea
            id="how_to_redeem"
            value={form.how_to_redeem}
            onChange={(event) => set({ how_to_redeem: event.target.value })}
            placeholder={"Open the pricing page.\nStart a new account.\nApply the code at checkout."}
            className="mt-1.5"
          />
        </div>

        <div className="space-y-2 rounded-lg border border-border p-3">
          {[
            { key: "is_genuinely_free" as const, label: "Genuinely free (never converts to a paid plan)" },
            { key: "requires_payment_method" as const, label: "Payment method required" },
            { key: "requires_student_id" as const, label: "Students only" },
          ].map((item) => (
            <label key={item.key} className="flex items-center gap-2 text-sm text-foreground/85">
              <input
                type="checkbox"
                checked={form[item.key]}
                onChange={(event) => set({ [item.key]: event.target.checked })}
                className="size-3.5 accent-lime-500"
              />
              {item.label}
            </label>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={submitting}>
            <Save className="size-4" />
            Save as draft
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={submitting}
            onClick={(event) => submit(event as unknown as React.FormEvent, true)}
          >
            Save and publish
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          Publishing makes the offer visible immediately with verification status{" "}
          <span className="font-medium">unverified</span>. Run a verification sweep afterwards to
          promote it to verified if the page checks out.
        </p>
      </form>
    </AdminShell>
  );
}