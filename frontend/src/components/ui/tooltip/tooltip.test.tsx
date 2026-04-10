import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./tooltip";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function BasicTooltip({
  content = "Tooltip text",
  defaultOpen,
}: {
  content?: string;
  defaultOpen?: boolean;
}) {
  return (
    // delayDuration=0 so we don't need to wait in hover tests
    // disableHoverableContent avoids keeping tooltip open when pointer moves toward content
    <TooltipProvider delayDuration={0} disableHoverableContent>
      <Tooltip defaultOpen={defaultOpen}>
        <TooltipTrigger>Hover me</TooltipTrigger>
        <TooltipContent>{content}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

describe("Tooltip", () => {
  it("renders the trigger", () => {
    render(<BasicTooltip />);
    expect(screen.getByText("Hover me")).toBeInTheDocument();
  });

  it("tooltip content is not visible before hover", () => {
    render(<BasicTooltip />);
    expect(document.querySelector("[data-slot=tooltip-content]")).not.toBeInTheDocument();
  });

  it("shows content when defaultOpen is true", () => {
    render(<BasicTooltip defaultOpen />);
    expect(document.querySelector("[data-slot=tooltip-content]")).toBeInTheDocument();
  });

  it("shows content on pointer enter", async () => {
    const user = userEvent.setup();
    render(<BasicTooltip />);
    await user.hover(screen.getByText("Hover me"));
    await screen.findAllByText("Tooltip text");
    expect(document.querySelector("[data-slot=tooltip-content]")).toBeInTheDocument();
  });

  it("hides content on pointer leave", async () => {
    const user = userEvent.setup();
    render(<BasicTooltip />);
    await user.hover(screen.getByText("Hover me"));
    await screen.findAllByText("Tooltip text");
    await user.unhover(screen.getByText("Hover me"));
    // Radix removes tooltip content from the DOM after pointer leave.
    expect(document.querySelector("[data-slot=tooltip-content]")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// TooltipContent
// ---------------------------------------------------------------------------

describe("TooltipContent", () => {
  it("renders with data-slot attribute", () => {
    render(<BasicTooltip defaultOpen />);
    expect(document.querySelector("[data-slot=tooltip-content]")).toBeInTheDocument();
  });

  it("merges custom className", () => {
    render(
      <TooltipProvider>
        <Tooltip defaultOpen>
          <TooltipTrigger>Trigger</TooltipTrigger>
          <TooltipContent className="custom-class">Content</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
    expect(document.querySelector("[data-slot=tooltip-content]")).toHaveClass("custom-class");
  });

  it("renders custom content", () => {
    render(
      <TooltipProvider>
        <Tooltip defaultOpen>
          <TooltipTrigger>Trigger</TooltipTrigger>
          <TooltipContent>
            <p>Custom content</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
    expect(document.querySelector("[data-slot=tooltip-content] p")).toHaveTextContent(
      "Custom content"
    );
  });
});

// ---------------------------------------------------------------------------
// TooltipProvider
// ---------------------------------------------------------------------------

describe("TooltipProvider", () => {
  it("renders children", () => {
    render(
      <TooltipProvider>
        <span>child</span>
      </TooltipProvider>
    );
    expect(screen.getByText("child")).toBeInTheDocument();
  });
});
