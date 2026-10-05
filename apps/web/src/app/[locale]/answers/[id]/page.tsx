import type { AnswerResponse, PublicConfig } from "@tibyan/contracts";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PermalinkAnswer } from "@/components/PermalinkAnswer";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { serverGet } from "@/lib/server-api";

export default async function AnswerPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  if (!isLocale(locale)) notFound();
  const dict = getDictionary(locale);
  const [answer, config] = await Promise.all([
    serverGet<AnswerResponse>(`/api/answers/${encodeURIComponent(id)}`),
    serverGet<PublicConfig>("/api/config").catch(() => null),
  ]);
  if (!answer) notFound();

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <Link href={`/${locale}`} className="text-sm text-muted hover:text-accent">
        ← {dict.ask.newQuestion}
      </Link>
      <div className="mt-6">
        <PermalinkAnswer
          answer={answer}
          locale={locale}
          dict={dict}
          ttsMode={config?.tts ?? "browser"}
        />
      </div>
    </div>
  );
}
