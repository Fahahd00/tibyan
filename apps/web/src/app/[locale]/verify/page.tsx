import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Flourish, StarMark } from "@/components/Ornament";
import { VerifyQuote } from "@/components/VerifyQuote";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: getDictionary(locale).verify.title } : {};
}

export default async function VerifyPage({ params }: Params) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const dict = getDictionary(locale);

  return (
    <div className="mx-auto max-w-3xl px-4 py-14 sm:px-6">
      <header className="text-center">
        <StarMark className="mx-auto h-9 w-9 text-gold" />
        <h1 className="mt-5 font-display text-4xl leading-tight text-ink sm:text-5xl">
          {dict.verify.title}
        </h1>
        <Flourish className="mt-5" />
        <p className="mx-auto mt-5 max-w-2xl text-pretty text-lg leading-9 text-muted">
          {dict.verify.intro}
        </p>
      </header>
      <div className="mt-10">
        <VerifyQuote locale={locale} dict={dict} />
      </div>
    </div>
  );
}
