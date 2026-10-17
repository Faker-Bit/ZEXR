import type { Metadata } from "next";
import { loadCategories } from "@/lib/categories";
import { AdminOfferEditor } from "./admin-offer-editor";
import type { Category } from "@/lib/types";

export const metadata: Metadata = {
  title: "New offer",
  robots: { index: false, follow: false },
};

export default async function NewOfferPage() {
  let categories: Category[] = [];
  try {
    categories = await loadCategories();
  } catch {
    categories = [];
  }
  return <AdminOfferEditor categories={categories} />;
}