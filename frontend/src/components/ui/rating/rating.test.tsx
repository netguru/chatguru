import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Rating, RatingStars, RatingSupportText, RatingTitle } from "./rating";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function BasicRating({
  defaultValue,
  value,
  onValueChange,
  disabled,
  readOnly,
}: {
  defaultValue?: number;
  value?: number;
  onValueChange?: (v: number) => void;
  disabled?: boolean;
  readOnly?: boolean;
}) {
  return (
    <Rating
      defaultValue={defaultValue}
      value={value}
      onValueChange={onValueChange}
      disabled={disabled}
      readOnly={readOnly}
    >
      <RatingTitle />
      <RatingStars />
      <RatingSupportText>Supporting text</RatingSupportText>
    </Rating>
  );
}

function getStars() {
  return screen.getAllByRole("radio");
}

// ---------------------------------------------------------------------------
// Rating
// ---------------------------------------------------------------------------

describe("Rating", () => {
  it("renders the root element with data-slot", () => {
    render(<BasicRating />);
    expect(
      document.querySelector("[data-slot=rating-stars]")?.closest("[data-slot=rating]")
    ).toBeInTheDocument();
  });

  it("renders 5 stars by default", () => {
    render(<BasicRating />);
    expect(getStars()).toHaveLength(5);
  });

  it("renders a custom max number of stars", () => {
    render(
      <Rating max={3}>
        <RatingStars />
      </Rating>
    );
    expect(screen.getAllByRole("radio")).toHaveLength(3);
  });

  it("renders children", () => {
    render(<BasicRating defaultValue={3} />);
    expect(screen.getByText("Supporting text")).toBeInTheDocument();
  });

  it("throws when useRating is used outside Rating", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<RatingStars />)).toThrow("useRating must be used within a Rating.");
    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// RatingStars — interaction
// ---------------------------------------------------------------------------

describe("RatingStars — interaction", () => {
  it("calls onValueChange with the clicked star value", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(<BasicRating onValueChange={onValueChange} />);
    await user.click(getStars()[2]); // 3rd star → value 3
    expect(onValueChange).toHaveBeenCalledWith(3);
  });

  it("does not call onValueChange when disabled", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(<BasicRating disabled onValueChange={onValueChange} />);
    await user.click(getStars()[2]);
    expect(onValueChange).not.toHaveBeenCalled();
  });

  it("does not call onValueChange when readOnly", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(<BasicRating readOnly onValueChange={onValueChange} />);
    await user.click(getStars()[2]);
    expect(onValueChange).not.toHaveBeenCalled();
  });

  it("updates internal value in uncontrolled mode", async () => {
    const user = userEvent.setup();
    render(<BasicRating />);
    await user.click(getStars()[3]); // 4th star → value 4
    expect(getStars()[3]).toBeChecked();
  });

  it("reflects controlled value", () => {
    render(<BasicRating value={2} />);
    expect(getStars()[1]).toBeChecked();
  });

  it("only the exact matching star is checked", () => {
    render(<BasicRating value={3} />);
    const stars = getStars();
    expect(stars[0]).not.toBeChecked();
    expect(stars[1]).not.toBeChecked();
    expect(stars[2]).toBeChecked();
    expect(stars[3]).not.toBeChecked();
    expect(stars[4]).not.toBeChecked();
  });

  it("stars are disabled when disabled prop is set", () => {
    render(<BasicRating disabled />);
    // biome-ignore lint/suspicious/useIterableCallbackReturn: getStars() returns an array, so forEach is appropriate here.
    getStars().forEach((star) => expect(star).toBeDisabled());
  });

  it("stars are not disabled when readOnly", () => {
    render(<BasicRating readOnly />);
    // biome-ignore lint/suspicious/useIterableCallbackReturn: getStars() returns an array, so forEach is appropriate here.
    getStars().forEach((star) => expect(star).not.toBeDisabled());
  });

  it("each star has a descriptive accessible name", () => {
    render(<BasicRating />);
    expect(screen.getByRole("radio", { name: "Rate 1 out of 5" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Rate 5 out of 5" })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// RatingTitle
// ---------------------------------------------------------------------------

describe("RatingTitle", () => {
  it("shows 0.0 when no value is selected", () => {
    render(<BasicRating defaultValue={0} />);
    expect(screen.getByText("0.0")).toBeInTheDocument();
  });

  it("shows selected value with one decimal place", () => {
    render(<BasicRating defaultValue={4} />);
    expect(screen.getByText("4.0")).toBeInTheDocument();
  });

  it("updates after clicking a star", async () => {
    const user = userEvent.setup();
    render(<BasicRating />);
    await user.click(getStars()[1]); // value 2
    expect(screen.getByText("2.0")).toBeInTheDocument();
  });

  it("applies data-slot attribute", () => {
    render(<BasicRating defaultValue={1} />);
    const el = screen.getByText("1.0");
    expect(el).toHaveAttribute("data-slot", "rating-title");
  });

  it("merges custom className", () => {
    render(
      <Rating defaultValue={1}>
        <RatingTitle className="custom-title" />
        <RatingStars />
      </Rating>
    );
    expect(screen.getByText("1.0")).toHaveClass("custom-title");
  });
});

// ---------------------------------------------------------------------------
// RatingSupportText
// ---------------------------------------------------------------------------

describe("RatingSupportText", () => {
  it("renders children", () => {
    render(<BasicRating />);
    expect(screen.getByText("Supporting text")).toBeInTheDocument();
  });

  it("applies data-slot attribute", () => {
    render(<BasicRating />);
    expect(screen.getByText("Supporting text")).toHaveAttribute("data-slot", "rating-support-text");
  });

  it("merges custom className", () => {
    render(
      <Rating>
        <RatingStars />
        <RatingSupportText className="custom-support">hint</RatingSupportText>
      </Rating>
    );
    expect(screen.getByText("hint")).toHaveClass("custom-support");
  });
});

// ---------------------------------------------------------------------------
// RatingStars — colour classes
// ---------------------------------------------------------------------------

describe("RatingStars — colour classes", () => {
  it("filled stars have data-filled, unfilled do not", async () => {
    const user = userEvent.setup();
    render(<BasicRating />);
    await user.click(getStars()[2]); // select 3
    expect(getStars()[0].closest("label")).toHaveAttribute("data-filled", "true");
    expect(getStars()[3].closest("label")).not.toHaveAttribute("data-filled");
  });

  it("disabled selected stars have data-selected, unselected do not", () => {
    render(<BasicRating disabled defaultValue={3} />);
    expect(getStars()[0].closest("label")).toHaveAttribute("data-selected", "true");
    expect(getStars()[3].closest("label")).not.toHaveAttribute("data-selected");
  });

  it("readOnly selected stars have data-selected, unselected do not", () => {
    render(<BasicRating readOnly defaultValue={3} />);
    expect(getStars()[0].closest("label")).toHaveAttribute("data-selected", "true");
    expect(getStars()[3].closest("label")).not.toHaveAttribute("data-selected");
  });
});
