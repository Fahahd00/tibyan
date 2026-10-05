import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <p className="font-display text-4xl text-ink">لم نجد هذه الصفحة</p>
      <p className="mt-3 text-muted">Page not found</p>
      <Link
        href="/ar"
        className="mt-8 inline-block rounded-full bg-accent px-5 py-2.5 text-sm text-white"
      >
        تِبْيان
      </Link>
    </div>
  );
}
