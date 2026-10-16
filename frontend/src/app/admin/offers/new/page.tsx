import type { Metadata } from "next";
import { api } from "@/lib/api";
import { AdminOfferEditor } from "./admin-offer-editor";
import type { Category } from "@/lib/types";

export const metadata: Metadata = {
  title: "New offer",
  robots: { index: false, follow: false },
};

export default async function NewOfferPage() {
  let categories: Category[] = [];
  try {
    categories = await api.categories();
  } catch {
    categories = [];
  }
  return <AdminOfferEditor categories={categories} />;
}