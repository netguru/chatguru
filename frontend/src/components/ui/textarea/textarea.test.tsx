import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  Textarea,
  TextareaCounter,
  TextareaField,
  TextareaHintText,
  TextareaLabel,
} from "./textarea";

describe("Textarea", () => {
  it("renders a textarea element", () => {
    render(<Textarea aria-label="Description" />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("renders with placeholder", () => {
    render(<Textarea placeholder="Enter description..." />);
    expect(screen.getByPlaceholderText("Enter description...")).toBeInTheDocument();
  });

  it("renders with a given value", () => {
    render(<Textarea value="hello" onChange={vi.fn()} />);
    expect(screen.getByRole("textbox")).toHaveValue("hello");
  });

  it("merges custom className", () => {
    render(<Textarea aria-label="Description" className="custom-class" />);
    expect(screen.getByRole("textbox")).toHaveClass("custom-class");
  });

  it("forwards ref", () => {
    const ref = createRef<HTMLTextAreaElement>();
    render(<Textarea ref={ref} aria-label="Description" />);
    expect(ref.current).toBeInstanceOf(HTMLTextAreaElement);
  });

  it("is disabled when disabled prop is passed", () => {
    render(<Textarea disabled aria-label="Description" />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });

  it("calls onChange when user types", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Textarea onChange={onChange} aria-label="Description" />);
    await user.type(screen.getByRole("textbox"), "hello");
    expect(onChange).toHaveBeenCalled();
  });

  it("accepts typed input", async () => {
    const user = userEvent.setup();
    render(<Textarea defaultValue="" aria-label="Description" />);
    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "hello world");
    expect(textarea).toHaveValue("hello world");
  });

  it("respects the rows attribute", () => {
    render(<Textarea rows={6} aria-label="Description" />);
    expect(screen.getByRole("textbox")).toHaveAttribute("rows", "6");
  });

  it("renders with maxLength attribute", () => {
    render(<Textarea maxLength={200} aria-label="Description" />);
    expect(screen.getByRole("textbox")).toHaveAttribute("maxlength", "200");
  });

  describe("aria-invalid", () => {
    it("forwards aria-invalid attribute", () => {
      render(<Textarea aria-invalid="true" aria-label="Description" />);
      expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
    });

    it("does not set aria-invalid attribute by default", () => {
      render(<Textarea aria-label="Description" />);
      expect(screen.getByRole("textbox")).not.toHaveAttribute("aria-invalid");
    });
  });
});

describe("TextareaField", () => {
  it("renders a div wrapper", () => {
    render(<TextareaField data-testid="root" />);
    expect(screen.getByTestId("root").tagName).toBe("DIV");
  });

  it("merges custom className", () => {
    render(<TextareaField data-testid="root" className="custom-root" />);
    expect(screen.getByTestId("root")).toHaveClass("custom-root");
  });

  it("renders children", () => {
    render(
      <TextareaField>
        <Textarea aria-label="Description" />
      </TextareaField>
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});

describe("TextareaLabel", () => {
  it("renders a label element with given text", () => {
    render(<TextareaLabel>My label</TextareaLabel>);
    expect(screen.getByText("My label").tagName).toBe("LABEL");
  });

  it("renders required asterisk when required prop is true", () => {
    render(<TextareaLabel required>Name</TextareaLabel>);
    expect(screen.getByText("*")).toBeInTheDocument();
  });

  it("does not render asterisk when required is not set", () => {
    render(<TextareaLabel>Name</TextareaLabel>);
    expect(screen.queryByText("*")).not.toBeInTheDocument();
  });

  it("associates label with textarea via htmlFor", () => {
    render(
      <>
        <TextareaLabel htmlFor="field">Label</TextareaLabel>
        <Textarea id="field" />
      </>
    );
    expect(screen.getByLabelText("Label")).toBeInTheDocument();
  });

  it("merges custom className", () => {
    render(<TextareaLabel className="custom-label">Label</TextareaLabel>);
    expect(screen.getByText("Label")).toHaveClass("custom-label");
  });
});

describe("TextareaHintText", () => {
  it("renders hint text", () => {
    render(<TextareaHintText>Helper text</TextareaHintText>);
    expect(screen.getByText("Helper text")).toBeInTheDocument();
  });

  it("always has base label text class", () => {
    render(<TextareaHintText>Helper text</TextareaHintText>);
    expect(screen.getByText("Helper text")).toHaveClass("text-text-label");
  });

  it("always has peer-aria-invalid class for automatic error styling", () => {
    render(<TextareaHintText>Hint</TextareaHintText>);
    expect(screen.getByText("Hint")).toHaveClass("peer-aria-invalid:text-semantic-error-strong");
  });

  it("merges custom className", () => {
    render(<TextareaHintText className="custom-hint">Hint</TextareaHintText>);
    expect(screen.getByText("Hint")).toHaveClass("custom-hint");
  });
});

describe("TextareaCounter", () => {
  it("renders current/max format", () => {
    render(<TextareaCounter current={50} max={200} />);
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText("/200")).toBeInTheDocument();
  });

  it("does not apply error class when within limit", () => {
    render(<TextareaCounter current={50} max={200} />);
    expect(screen.getByText("50")).not.toHaveClass("text-semantic-error-strong");
  });

  it("applies error color when over limit", () => {
    render(<TextareaCounter current={210} max={200} />);
    expect(screen.getByText("210")).toHaveClass("text-semantic-error-strong");
  });

  it("does not apply error class when exactly at limit", () => {
    render(<TextareaCounter current={200} max={200} />);
    expect(screen.getByText("200")).not.toHaveClass("text-semantic-error-strong");
  });

  it("current has group-has-focus:text-text-interactive class", () => {
    render(<TextareaCounter current={50} max={200} />);
    expect(screen.getByText("50")).toHaveClass("group-has-focus:text-text-interactive");
  });

  it("merges custom className on wrapper", () => {
    render(<TextareaCounter current={10} max={100} className="custom-counter" />);
    expect(screen.getByText("10").parentElement).toHaveClass("custom-counter");
  });
});
