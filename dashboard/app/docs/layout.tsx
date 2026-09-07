import type { ReactNode } from 'react';

import { DocsSidebar } from '@/components/docs/DocsSidebar';
import { SiteFooter } from '@/components/site/SiteFooter';
import { SiteHeader } from '@/components/site/SiteHeader';

/**
 * app/docs/layout.tsx — shared chrome for every docs page:
 * site header on top, sticky sidebar (search + nav) beside the
 * article, site footer below. Print styles strip the chrome.
 */

export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6 lg:flex-row lg:gap-10 lg:py-10">
        <DocsSidebar />
        <main className="min-w-0 flex-1 pb-16">
          <article className="mx-auto max-w-3xl">{children}</article>
        </main>
      </div>
      <SiteFooter />
    </div>
  );
}
