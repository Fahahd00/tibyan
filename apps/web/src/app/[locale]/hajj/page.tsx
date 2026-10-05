import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AskExperience } from "@/components/AskExperience";
import { Flourish, MihrabArch, StarMark } from "@/components/Ornament";
import { QrPoster } from "@/components/QrPoster";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: getDictionary(locale).hajj.title } : {};
}

/** Pilgrims: questions on Hajj, Umrah and the Two Holy Mosques, in the pilgrim's language and by voice. */
export default async function HajjPage({ params }: Params) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const dict = getDictionary(locale);

  return (
    <>
      <section className="mx-auto max-w-6xl px-4 pt-10 sm:px-6 sm:pt-14">
        <div className="relative mx-auto max-w-xl px-6 pb-9 pt-14 text-center sm:px-12 sm:pt-16">
          <MihrabArch className="absolute inset-0 h-full w-full text-gold/50" />
          <StarMark className="absolute left-1/2 top-0 h-5 w-5 -translate-x-1/2 -translate-y-1/3 bg-paper text-gold" />
          <p className="text-sm text-muted">{dict.hajj.welcome}</p>
          <h1 className="mt-4 font-display text-5xl leading-[1.4] text-ink sm:text-6xl">
            {dict.hajj.title}
          </h1>
          <Flourish className="mt-4" />
        </div>
        <p className="mx-auto mt-8 max-w-2xl text-balance text-center text-lg leading-9 text-ink-2">
          {dict.hajj.lead}
        </p>
        <div className="mt-8">
          <AskExperience locale={locale} dict={dict} examples={dict.hajj.examples} />
        </div>
      </section>
      <div className="mx-auto max-w-3xl px-4 pt-14 sm:px-6">
        <QrPoster locale={locale} dict={dict} />
      </div>
    </>
  );
}
