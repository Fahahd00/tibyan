import { notFound } from "next/navigation";
import { AdminConsole } from "@/components/AdminConsole";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export const metadata = { robots: { index: false } };

export default async function AdminPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const dict = getDictionary(locale);
  return (
    <div className="mx-auto max-w-5xl px-4 py-14 sm:px-6">
      <h1 className="font-display text-4xl text-ink">{dict.admin.title}</h1>
      <p className="mt-4 max-w-2xl leading-8 text-muted">{dict.admin.intro}</p>
      <AdminConsole locale={locale} dict={dict} />
    </div>
  );
}
