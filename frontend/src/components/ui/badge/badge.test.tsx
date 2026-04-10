import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it } from "vitest";
import { Badge } from "./badge";

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>New</Badge>);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("renders as a span element", () => {
    render(<Badge>Label</Badge>);
    expect(screen.getByText("Label").tagName).toBe("SPAN");
  });

  it("merges custom className", () => {
    render(<Badge className="custom-class">Label</Badge>);
    expect(screen.getByText("Label")).toHaveClass("custom-class");
  });

  it("forwards ref", () => {
    const ref = createRef<HTMLSpanElement>();
    render(<Badge ref={ref}>Label</Badge>);
    expect(ref.current).toBeInstanceOf(HTMLSpanElement);
  });

  it("forwards additional props", () => {
    render(<Badge data-testid="badge">Label</Badge>);
    expect(screen.getByTestId("badge")).toBeInTheDocument();
  });

  it("applies default variant and type classes when no props provided", () => {
    render(<Badge>Label</Badge>);
    const el = screen.getByText("Label");
    expect(el).toHaveClass("bg-surface-neutral-stronger", "text-text-inverted");
  });

  describe("strong emphasis", () => {
    it("applies default/strong classes", () => {
      render(
        <Badge variant="default" type="strong">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass(
        "bg-surface-neutral-stronger",
        "text-text-inverted"
      );
    });

    it("applies brand/strong classes", () => {
      render(
        <Badge variant="brand" type="strong">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass(
        "bg-surface-interactive-strong",
        "text-text-inverted"
      );
    });

    it("applies positive/strong classes", () => {
      render(
        <Badge variant="positive" type="strong">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass(
        "bg-semantic-success-strong",
        "text-text-inverted"
      );
    });

    it("applies attention/strong classes", () => {
      render(
        <Badge variant="attention" type="strong">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass("text-text-inverted");
    });

    it("applies critical/strong classes", () => {
      render(
        <Badge variant="critical" type="strong">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass(
        "bg-semantic-error-strong",
        "text-text-inverted"
      );
    });
  });

  describe("soft emphasis", () => {
    it("applies default/soft classes", () => {
      render(
        <Badge variant="default" type="soft">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass("bg-surface-neutral-medium", "text-text-title");
    });

    it("applies brand/soft classes", () => {
      render(
        <Badge variant="brand" type="soft">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass(
        "bg-surface-interactive-medium",
        "text-text-interactive"
      );
    });

    it("applies positive/soft classes", () => {
      render(
        <Badge variant="positive" type="soft">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass(
        "bg-semantic-success-medium",
        "text-text-title"
      );
    });

    it("applies attention/soft classes", () => {
      render(
        <Badge variant="attention" type="soft">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass(
        "bg-semantic-warning-medium",
        "text-text-title"
      );
    });

    it("applies critical/soft classes", () => {
      render(
        <Badge variant="critical" type="soft">
          Label
        </Badge>
      );
      expect(screen.getByText("Label")).toHaveClass("bg-semantic-error-medium", "text-text-title");
    });
  });
});
