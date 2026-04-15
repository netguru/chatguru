import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Teach tailwind-merge about custom design tokens from tokens.css.
// Without this, twMerge conflates custom token classes with similarly-prefixed
// built-in groups and incorrectly removes classes (e.g. text-t4 removed by text-text-inverted).
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      // --text-{name} → font-size utilities (text-t4, text-h1, text-display, …)
      "font-size": [
        {
          text: [
            "display",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "t1",
            "t2",
            "t3",
            "t4",
            "t5",
            "button-l",
            "button-m",
            "button-s",
            "display-tablet",
            "h1-tablet",
            "h2-tablet",
            "h3-tablet",
            "h4-tablet",
            "h5-tablet",
            "h6-tablet",
            "t1-tablet",
            "t2-tablet",
            "t3-tablet",
            "t4-tablet",
            "t5-tablet",
            "button-l-tablet",
            "button-m-tablet",
            "button-s-tablet",
            "display-mobile",
            "h1-mobile",
            "h2-mobile",
            "h3-mobile",
            "h4-mobile",
            "h5-mobile",
            "h6-mobile",
            "t1-mobile",
            "t2-mobile",
            "t3-mobile",
            "t4-mobile",
            "t5-mobile",
            "button-l-mobile",
            "button-m-mobile",
            "button-s-mobile",
          ],
        },
      ],
      // --tracking-{name} → letter-spacing utilities (tracking-s/m/l)
      tracking: [{ tracking: ["s", "m", "l"] }],
      // --leading-{name} → line-height utilities (leading-s/m/l/xl/2xl)
      leading: [{ leading: ["s", "m", "l", "xl", "2xl"] }],
      // --shadow-{name} → box-shadow utilities
      shadow: [
        {
          shadow: [
            "small-top-light",
            "medium-top-light",
            "large-top-light",
            "small-bottom-light",
            "medium-bottom-light",
            "large-bottom-light",
          ],
        },
      ],
      // --radius-{name} → border-radius utilities (rounded-xs/s/m/l/rounded)
      rounded: [{ rounded: ["xs", "s", "m", "l", "rounded"] }],
      // --font-weight-{name} → font-weight utilities (font-weight-soft/medium/strong)
      "font-weight": [{ "font-weight": ["soft", "medium", "strong"] }],
      // --border-1-5 → border-width utility (border-1-5)
      "border-w": [{ border: ["1-5"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
