"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "./ThemeProvider";

const links = [
  { href: "/environment", label: "Environment" },
  { href: "/tasks", label: "Tasks" },
  { href: "/results", label: "Results" },
];

const external = [
  { href: "#", label: "Paper" },
  { href: "#", label: "GitHub" },
];

export function Nav() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();

  return (
    <nav className="flex justify-between items-center w-full px-6 py-4">
      <Link href="/" className="text-[15px] font-semibold text-[var(--text-primary)] tracking-tight no-underline">
        WebAgentBench
      </Link>
      <div className="flex items-center gap-1 bg-[var(--surface)] rounded-xl p-1">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`no-underline text-[13px] px-4 py-[6px] rounded-[10px] transition-colors duration-150 ${
              pathname.startsWith(link.href)
                ? "bg-[var(--bg)] text-[var(--text-primary)] font-medium"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {link.label}
          </Link>
        ))}
      </div>
      <div className="flex items-center gap-6 text-[13px] text-[var(--text-secondary)]">
        {external.map((link) => (
          <a
            key={link.label}
            href={link.href}
            className="no-underline text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors duration-150"
          >
            {link.label}
          </a>
        ))}
        <button
          onClick={toggle}
          aria-label="Toggle theme"
          className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface)] transition-colors duration-150"
        >
          {theme === "dark" ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>
      </div>
    </nav>
  );
}
