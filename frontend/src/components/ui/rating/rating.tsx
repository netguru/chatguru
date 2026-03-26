"use client";

import { StarIcon } from "@phosphor-icons/react/Star";
import * as React from "react";

import { cn } from "../../../utils/utils";

/*
 * -------
 * Context
 * -------
 */

type RatingContextProps = {
  value: number;
  hoverValue: number;
  setHoverValue: (value: number) => void;
  handleSelect: (value: number) => void;
  disabled: boolean;
  readOnly: boolean;
  max: number;
};

const RatingContext = React.createContext<RatingContextProps | null>(null);

function useRating() {
  const context = React.useContext(RatingContext);
  if (!context) throw new Error("useRating must be used within a Rating.");
  return context;
}

/*
 * ------
 * Rating
 * ------
 */

type RatingProps = React.ComponentProps<"div"> & {
  defaultValue?: number;
  value?: number;
  onValueChange?: (value: number) => void;
  disabled?: boolean;
  readOnly?: boolean;
  max?: number;
};

function Rating({
  defaultValue = 0,
  value: valueProp,
  onValueChange,
  disabled = false,
  readOnly = false,
  max = 5,
  className,
  children,
  ...props
}: RatingProps) {
  const [_value, _setValue] = React.useState(defaultValue);
  const value = valueProp !== undefined ? valueProp : _value;
  const [hoverValue, setHoverValue] = React.useState(0);

  const handleSelect = React.useCallback(
    (v: number) => {
      if (disabled || readOnly) return;
      if (valueProp === undefined) _setValue(v);
      onValueChange?.(v);
    },
    [disabled, readOnly, valueProp, onValueChange]
  );

  const contextValue = React.useMemo<RatingContextProps>(
    () => ({ value, hoverValue, setHoverValue, handleSelect, disabled, readOnly, max }),
    [value, hoverValue, handleSelect, disabled, readOnly, max]
  );

  return (
    <RatingContext.Provider value={contextValue}>
      <div
        data-slot="rating"
        data-disabled={disabled || undefined}
        data-readonly={readOnly || undefined}
        className={cn("group/rating flex flex-col gap-2", className)}
        {...props}
      >
        {children}
      </div>
    </RatingContext.Provider>
  );
}
Rating.displayName = "Rating";

/*
 * -----------
 * RatingTitle
 * -----------
 */

type RatingTitleProps = React.ComponentProps<"div">;

function RatingTitle({ className, children, ...props }: RatingTitleProps) {
  const { value } = useRating();

  return (
    <div
      data-slot="rating-title"
      className={cn("text-h2 font-strong text-text-title text-center tracking-l", className)}
      {...props}
    >
      {children ?? value.toFixed(1)}
    </div>
  );
}
RatingTitle.displayName = "RatingTitle";

/*
 * -----------
 * RatingStars
 * -----------
 */

type RatingStarsProps = Omit<React.ComponentProps<"fieldset">, "children" | "disabled"> & {
  legend?: string;
  getStarLabel?: (starValue: number, max: number) => string;
};

function RatingStars({ className, legend, getStarLabel, ...props }: RatingStarsProps) {
  const { value, hoverValue, setHoverValue, handleSelect, disabled, readOnly, max } = useRating();

  const groupName = React.useId();
  const activeValue = !disabled && !readOnly && hoverValue > 0 ? hoverValue : value;

  return (
    <fieldset
      data-slot="rating-stars"
      className={cn("border-0 p-0 m-0 min-w-0 flex gap-2", className)}
      onMouseLeave={() => !disabled && !readOnly && setHoverValue(0)}
      {...props}
    >
      <legend className="sr-only">{legend ?? "Rating"}</legend>
      {Array.from({ length: max }, (_, i) => {
        const starValue = i + 1;
        const isFilled = starValue <= activeValue;
        const isActuallySelected = starValue <= value;

        return (
          <label
            key={starValue}
            data-filled={isFilled || undefined}
            data-selected={isActuallySelected || undefined}
            onMouseEnter={() => !disabled && !readOnly && setHoverValue(starValue)}
            className={cn(
              /* Layout */
              "rounded-s transition-colors",
              /* Focus visible */
              "has-focus-visible:outline-none has-focus-visible:ring-2 has-focus-visible:ring-focus-ring",
              "has-focus-visible:ring-offset-2 has-focus-visible:ring-offset-white",
              /* Cursor */
              "cursor-pointer",
              "group-data-disabled/rating:cursor-not-allowed",
              "group-data-readonly/rating:cursor-default",
              /* Colours */
              "text-surface-neutral-medium",
              "data-filled:text-surface-interactive-strong",
              "group-data-disabled/rating:text-surface-disabled-base",
              "group-data-disabled/rating:data-selected:text-text-disabled-interactive",
              "group-data-readonly/rating:data-selected:text-semantic-warning-active-medium"
            )}
          >
            <input
              type="radio"
              name={groupName}
              value={starValue}
              checked={value === starValue}
              disabled={disabled}
              onChange={() => {
                if (!readOnly) handleSelect(starValue);
              }}
              className="sr-only"
            />
            <span className="sr-only">
              {getStarLabel ? getStarLabel(starValue, max) : `Rate ${starValue} out of ${max}`}
            </span>
            <StarIcon weight="fill" className="size-11 shrink-0 pointer-events-none" />
          </label>
        );
      })}
    </fieldset>
  );
}
RatingStars.displayName = "RatingStars";

/*
 * -----------------
 * RatingSupportText
 * -----------------
 */

type RatingSupportTextProps = React.ComponentProps<"p">;

function RatingSupportText({ className, ...props }: RatingSupportTextProps) {
  return (
    <p
      data-slot="rating-support-text"
      className={cn("text-t3 text-text-tertiary font-medium text-center tracking-s", className)}
      {...props}
    />
  );
}
RatingSupportText.displayName = "RatingSupportText";

/*
 * -------
 * Exports
 * -------
 */

export type { RatingProps, RatingStarsProps, RatingSupportTextProps, RatingTitleProps };
export { Rating, RatingStars, RatingSupportText, RatingTitle, useRating };
