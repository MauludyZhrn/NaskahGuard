import React from "react";

interface PageHeaderProps {
  title: string;
  description: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, description, badge, actions }) => (
  <header className="mb-6 flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-end md:justify-between">
    <div className="flex flex-col gap-1.5 min-w-0">
      <div className="flex flex-wrap items-center gap-2.5">
        <h1 className="font-serif text-2xl font-bold tracking-tight text-foreground md:text-[26px]">
          {title}
        </h1>
        {badge}
      </div>
      <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>}
  </header>
);
