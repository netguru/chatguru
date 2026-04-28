import type { ComponentProps } from "react";

export type LogoProps = Omit<ComponentProps<"img">, "src">;

export function Logo({ alt = "", className, ...props }: LogoProps) {
  return (
    <img
      src="/branding/chatguru-logotype.svg"
      alt={alt}
      className={className}
      decoding="async"
      draggable={false}
      {...props}
    />
  );
}