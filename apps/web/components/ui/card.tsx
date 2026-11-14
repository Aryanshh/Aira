import * as React from "react";
import { cn } from "@/lib/utils";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-card border border-border bg-surface text-text-main shadow-soft p-5 md:p-6",
        className
      )}
      {...props}
    />
  )
);
Card.displayName = "Card";

export { Card };
