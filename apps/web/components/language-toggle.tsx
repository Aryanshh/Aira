"use client";

import { useLocale } from "next-intl";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "./ui/button";

export function LanguageToggle() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const toggleLanguage = () => {
    const nextLocale = locale === "en" ? "hi" : "en";
    // Replace leading locale in current path
    const pathWithoutLocale = pathname.replace(`/${locale}`, "") || "/";
    router.push(`/${nextLocale}${pathWithoutLocale}`);
  };

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleLanguage}
      className="font-medium text-sm flex items-center gap-1.5"
      aria-label="Toggle language between English and Hindi"
    >
      <span>🌐</span>
      <span>{locale === "en" ? "हिन्दी" : "English"}</span>
    </Button>
  );
}
