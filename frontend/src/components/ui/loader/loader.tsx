import { cn } from "../../../utils/utils";

export type LoaderPops = React.ComponentProps<"span">;

export function Loader({ className }: LoaderPops) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn("basis-full flex items-center gap-0.5", className)}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          aria-hidden="true"
          style={{ animationDelay: `${i * 0.15}s` }}
          className={cn(
            "bg-text-primary",
            "text-text-primary",
            "rounded-full",
            "size-2",
            "animate-bounce"
          )}
        />
      ))}
    </span>
  );
}
