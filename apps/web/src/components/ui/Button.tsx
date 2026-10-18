import React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "danger" | "ghost" | "dark";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const variantStyles = {
    primary:
      "bg-[#FF5722] hover:bg-[#E84A1A] text-white font-semibold shadow-md shadow-orange-500/20 active:translate-y-px",
    secondary:
      "bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 shadow-xs active:translate-y-px",
    outline:
      "bg-transparent hover:bg-slate-100/70 text-slate-700 border border-slate-300 hover:border-slate-400 active:translate-y-px",
    danger:
      "bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 active:translate-y-px",
    ghost: "bg-transparent hover:bg-slate-100 text-slate-600 hover:text-slate-900",
    dark: "bg-[#18191B] hover:bg-black text-white font-medium active:translate-y-px shadow-xs",
  };

  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs rounded-lg gap-1.5",
    md: "px-4 py-2 text-sm rounded-xl gap-2",
    lg: "px-6 py-2.5 text-sm sm:text-base rounded-xl gap-2 font-bold",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed select-none focus:outline-none focus:ring-2 focus:ring-[#FF5722]/30",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <svg
          className="animate-spin -ml-1 mr-2 h-4 w-4 text-current"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}
