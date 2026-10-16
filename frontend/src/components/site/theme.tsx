"use client";

import * as React from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "zexrdealhub-theme";
const CHANGE_EVENT = "zexrdealhub-theme-change";

/**
 * The stored preference lives in localStorage, which is an *external store*.
 * Reading it through `useSyncExternalStore` (rather than `useState` plus an
 * effect) means the server renders the documented default, the client picks up
 * the real value at hydration, and neither path triggers a cascading render.
 */
const themeStore = {
  subscribe(onChange: () => void) {
    window.addEventListener(CHANGE_EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  },
  get(): Theme {
    return (window.localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "dark";
  },
  getServerSnapshot(): Theme {
    return "dark";
  },
};

/** `false` on the server, `true` after hydration — without a setState effect. */
const emptySubscribe = () => () => undefined;
const useHydrated = () =>
  React.useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );

/**
 * Dark-first theming.
 *
 * The inline script in the layout applies the stored preference before paint
 * so there is no flash of the wrong theme.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = React.useSyncExternalStore(
    themeStore.subscribe,
    themeStore.get,
    themeStore.getServerSnapshot,
  );

  const apply = React.useCallback((next: Theme) => {
    const root = document.documentElement;
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = next === "dark" || (next === "system" && prefersDark);
    root.classList.toggle("dark", dark);
    root.style.colorScheme = dark ? "dark" : "light";
    window.localStorage.setItem(STORAGE_KEY, next);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  React.useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => theme === "system" && apply("system");
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [theme, apply]);

  const setTheme = React.useCallback(
    (next: Theme) => {
      apply(next);
    },
    [apply],
  );

  const value = React.useMemo(() => ({ theme, setTheme }), [theme, setTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = React.createContext<ThemeContextValue>({
  theme: "dark",
  setTheme: () => undefined,
});

export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem('${STORAGE_KEY}') || 'dark';
    var dark = stored === 'dark' || (stored === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', dark);
    document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
  } catch (e) {}
})();
`;

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = React.useContext(ThemeContext);
  const mounted = useHydrated();

  const options: { value: Theme; icon: React.ElementType; label: string }[] = [
    { value: "light", icon: Sun, label: "Light" },
    { value: "dark", icon: Moon, label: "Dark" },
    { value: "system", icon: Monitor, label: "System" },
  ];

  return (
    <div
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg border border-border bg-background/60 p-0.5",
        className,
      )}
      role="group"
      aria-label="Colour theme"
    >
      {options.map((option) => {
        const Icon = option.icon;
        const active = mounted && theme === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => setTheme(option.value)}
            aria-label={option.label}
            aria-pressed={active}
            className={cn(
              "flex size-7 items-center justify-center rounded-md transition-colors",
              active ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-3.5" />
          </button>
        );
      })}
    </div>
  );
}

export function useTheme() {
  return React.useContext(ThemeContext);
}