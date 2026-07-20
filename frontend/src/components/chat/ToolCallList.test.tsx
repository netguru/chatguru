import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { ToolCall } from "../../types/chat";
import { ToolCallList } from "./ToolCallList";

const calls: ToolCall[] = [
  { name: "search_documents", args: { query: "pricing" }, result: "3 docs", status: "done" },
];

describe("ToolCallList", () => {
  it("renders a chip per tool call and expands to show args and result", async () => {
    render(<ToolCallList toolCalls={calls} />);
    const chip = screen.getByRole("button", { name: /search_documents/ });
    expect(chip).toBeInTheDocument();
    // Collapsed: details not shown.
    expect(chip).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/pricing/)).not.toBeInTheDocument();
    await userEvent.click(chip);
    // Expanded: args + result visible.
    expect(chip).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/pricing/)).toBeInTheDocument();
    expect(screen.getByText(/3 docs/)).toBeInTheDocument();
  });

  it("renders nothing when there are no tool calls", () => {
    const { container } = render(<ToolCallList toolCalls={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
