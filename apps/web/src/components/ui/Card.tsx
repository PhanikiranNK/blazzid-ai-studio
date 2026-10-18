import React from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
}

export function Card({ className, elevated = false, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-[24px] sm:rounded-[32px] border transition-all duration-200",
        elevated
          ? "bg-white border-[#E2E8E2] shadow-sm shadow-slate-900/4"
          : "bg-white border-[#E5EBE5] shadow-xs",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("px-6 sm:px-8 py-5 border-b border-[#EEF2EE]", className)} {...props}>
      {children}
    </div>
  );
}

export function CardContent({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("p-6 sm:p-8", className)} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("px-6 sm:px-8 py-4 border-t border-[#EEF2EE] bg-[#FAFBF9]/80 rounded-b-[24px] sm:rounded-b-[32px]", className)} {...props}>
      {children}
    </div>
  );
}
