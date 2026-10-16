"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bookmark,
  Compass,
  Gamepad2 as GamepadIcon,
  LayoutDashboard,
  LogIn,
  Menu,
Plus,
    ShieldCheck,
    Sparkles as SparklesIcon,
    User as UserIcon,
  } from "lucide-react";
import { Logo } from "./logo";
import { SearchBar } from "./search-bar";
import { ThemeToggle } from "./theme";
import { useAuth } from "./auth-provider";
import { Sheet } from "@/components/ui/overlays";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Category } from "@/lib/types";

interface HeaderProps {
  categories: Category[];
}

const NAV = [
  { href: "/offers", label: "All offers", icon: Compass },
  { href: "/offers?type=free_trial", label: "Free trials", icon: SparkleIcon },
  { href: "/offers?type=free", label: "Free tools", icon: Bookmark },
  { href: "/gaming", label: "Free games", icon: GamepadIcon },
  { href: "/categories", label: "Categories", icon: GridIcon },
  { href: "/expired", label: "Recently expired", icon: ClockIcon },
];

export function Header({ categories }: HeaderProps) {
  const pathname = usePathname();
  const { user } = useAuth();
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [scrolled, setScrolled] = React.useState(false);
  const [categoryOpen, setCategoryOpen] = React.useState(false);

  React.useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 8);
    handler();
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  React.useEffect(() => setMenuOpen(false), [pathname]);

  const popular = categories.filter((category) => category.offer_count > 0).slice(0, 14);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full border-b transition-all duration-200",
        scrolled
          ? "border-border bg-background/85 backdrop-blur-xl supports-[backdrop-filter]:bg-background/70"
          : "border-transparent bg-background",
      )}
    >
      <div className="container flex h-16 items-center gap-3">
        <button
          type="button"
          className="flex size-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:text-foreground lg:hidden"
          onClick={() => setMenuOpen(true)}
          aria-label="Open navigation"
        >
          <Menu className="size-4" />
        </button>

        <Logo />

        <nav className="ml-4 hidden items-center gap-0.5 lg:flex">
          <NavLink href="/offers" active={pathname === "/offers"}>
            Browse
          </NavLink>
          <div
            className="relative"
            onMouseEnter={() => setCategoryOpen(true)}
            onMouseLeave={() => setCategoryOpen(false)}
          >
            <NavLink href="/categories" active={pathname.startsWith("/categories")}>
              Categories
            </NavLink>
            {categoryOpen ? (
              <div className="absolute left-0 top-full w-[560px] pt-2">
                <div className="animate-fade-up rounded-xl border border-border bg-popover/97 p-2 shadow-2xl backdrop-blur">
                  <div className="grid grid-cols-2 gap-0.5">
                    {popular.map((category) => (
                      <Link
                        key={category.slug}
                        href={`/categories/${category.slug}`}
                        className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors hover:bg-accent"
                      >
                        <span className="truncate text-foreground/90">{category.name}</span>
                        <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
                          {category.offer_count}
                        </span>
                      </Link>
                    ))}
                  </div>
                  <Link
                    href="/categories"
                    className="mt-1 block rounded-lg px-2.5 py-2 text-center text-xs font-medium text-primary hover:bg-accent"
                  >
                    All {categories.length} categories →
                  </Link>
                </div>
              </div>
            ) : null}
          </div>
          <NavLink href="/offers?type=free_trial" active={false}>
            Free trials
          </NavLink>
          <NavLink href="/expired" active={pathname === "/expired"}>
            Expired
          </NavLink>
        </nav>

        <div className="ml-auto hidden w-full max-w-md xl:block">
          <SearchBar size="sm" />
        </div>

        <div className="ml-auto flex items-center gap-2 xl:ml-3">
          <Button asChild size="sm" variant="outline" className="hidden sm:inline-flex">
            <Link href="/submit">
              <Plus className="size-3.5" />
              Submit
            </Link>
          </Button>

          <ThemeToggle className="hidden sm:inline-flex" />

          {user ? (
            <Button asChild size="icon-sm" variant="ghost" title="Admin panel">
              <Link href="/admin">
                <LayoutDashboard className="size-4" />
              </Link>
            </Button>
          ) : null}
        </div>
      </div>

      <div className="container pb-3 xl:hidden">
        <SearchBar size="sm" />
      </div>

      <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title="Browse" side="left">
        <nav className="flex flex-col gap-0.5 p-3">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:bg-accent"
            >
              <item.icon className="size-4 text-muted-foreground" />
              {item.label}
            </Link>
          ))}
          <div className="my-2 h-px bg-border" />
          <Link
            href="/submit"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium hover:bg-accent"
          >
            <Plus className="size-4 text-muted-foreground" />
            Submit a deal
          </Link>
          <Link
            href="/trust-and-safety"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium hover:bg-accent"
          >
            <ShieldCheck className="size-4 text-muted-foreground" />
            Trust &amp; safety
          </Link>
          <div className="mt-3 flex items-center justify-between px-3">
            <ThemeToggle />
            {!user ? (
              <Button asChild size="sm">
                <Link href="/login">Admin sign in</Link>
              </Button>
            ) : null}
          </div>
        </nav>
        <div className="border-t border-border p-3">
          <p className="mb-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Categories
          </p>
          <div className="flex flex-wrap gap-1.5">
            {categories.slice(0, 18).map((category) => (
              <Link
                key={category.slug}
                href={`/categories/${category.slug}`}
                className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                {category.name}
              </Link>
            ))}
          </div>
        </div>
      </Sheet>
    </header>
  );
}

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors",
        active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </Link>
  );
}

function SparkleIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
    </svg>
  );
}

function GridIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <rect x="3" y="3" width="7" height="7" rx="2" />
      <rect x="14" y="3" width="7" height="7" rx="2" />
      <rect x="3" y="14" width="7" height="7" rx="2" />
      <rect x="14" y="14" width="7" height="7" rx="2" />
    </svg>
  );
}

function ClockIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}