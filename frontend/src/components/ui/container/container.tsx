import type { ComponentProps } from "react";
import { cn } from "../../../utils/utils";

interface ContainerProps extends ComponentProps<"div"> {
  className?: string;
}

export const Container = ({ children, className, ...props }: ContainerProps) => (
  <div className={cn("w-full max-w-3xl mx-auto px-5 md:px-8 py-6", className)} {...props}>
    {children}
  </div>
);
