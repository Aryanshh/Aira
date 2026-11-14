import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "sos" | "warning";
  size?: "default" | "sm" | "lg" | "elder";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "default", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-bold transition-colors focus-visible:outline focus-visible:outline-3 focus-visible:outline-primary disabled:pointer-events-none disabled:opacity-50 select-none",
          // Variants
          variant === "primary" && "bg-primary text-white hover:bg-opacity-95 shadow-soft",
          variant === "secondary" && "bg-secondary text-white hover:bg-opacity-95 shadow-soft",
          variant === "sos" && "bg-sos text-white hover:bg-opacity-95 shadow-lg",
          variant === "warning" && "bg-warning-bg text-warning border border-warning hover:bg-opacity-80",
          variant === "outline" && "border-2 border-border bg-surface text-text-main hover:bg-surface-soft",
          variant === "ghost" && "text-text-main hover:bg-surface-soft",
          // Sizes
          size === "default" && "h-12 px-6 rounded-btn text-base",
          size === "sm" && "h-10 px-4 rounded-btn text-sm",
          size === "lg" && "h-14 px-8 rounded-btn text-lg",
          size === "elder" && "h-16 px-8 rounded-btn text-xl min-h-[64px]",
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
