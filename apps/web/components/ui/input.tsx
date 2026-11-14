import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, label, error, id, ...props }, ref) => {
    const generatedId = React.useId();
    const inputId = id || generatedId;

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-semibold text-text-main">
            {label}
          </label>
        )}
        <input
          id={inputId}
          type={type}
          ref={ref}
          className={cn(
            "flex h-12 w-full rounded-input border border-border bg-surface px-4 py-2 text-base text-text-main placeholder:text-text-muted focus-visible:outline focus-visible:outline-3 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50",
            error && "border-warning text-warning focus-visible:outline-warning",
            className
          )}
          {...props}
        />
        {error && <p className="text-sm font-medium text-warning">{error}</p>}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };
