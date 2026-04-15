import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  Modal,
  ModalBody,
  ModalClose,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalTitle,
  ModalTrigger,
} from "./modal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function BasicModal({
  onOpenChange,
  showCloseButton,
}: {
  onOpenChange?: (open: boolean) => void;
  showCloseButton?: boolean;
}) {
  return (
    <Modal onOpenChange={onOpenChange}>
      <ModalTrigger>Open</ModalTrigger>
      <ModalContent showCloseButton={showCloseButton}>
        <ModalHeader>
          <ModalTitle>Modal title</ModalTitle>
          <ModalBody>Modal description</ModalBody>
        </ModalHeader>
        <ModalFooter>
          <ModalClose>Dismiss</ModalClose>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

describe("Modal", () => {
  it("renders the trigger", () => {
    render(<BasicModal />);
    expect(screen.getByText("Open")).toBeInTheDocument();
  });

  it("dialog is not visible before trigger click", () => {
    render(<BasicModal />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the dialog on trigger click", async () => {
    const user = userEvent.setup();
    render(<BasicModal />);
    await user.click(screen.getByText("Open"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("renders title and description when open", async () => {
    const user = userEvent.setup();
    render(<BasicModal />);
    await user.click(screen.getByText("Open"));
    expect(screen.getByText("Modal title")).toBeInTheDocument();
    expect(screen.getByText("Modal description")).toBeInTheDocument();
  });

  it("closes the dialog via the footer close button", async () => {
    const user = userEvent.setup();
    render(<BasicModal />);
    await user.click(screen.getByText("Open"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("calls onOpenChange when dialog opens and closes", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(<BasicModal onOpenChange={onOpenChange} />);
    await user.click(screen.getByText("Open"));
    expect(onOpenChange).toHaveBeenCalledWith(true);
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("closes the dialog via the X icon close button", async () => {
    const user = userEvent.setup();
    render(<BasicModal />);
    await user.click(screen.getByText("Open"));
    await user.click(screen.getByRole("button", { name: "Close" }));
    // The X icon button has aria-label="Close" and is the only button with that name
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the dialog on Escape key", async () => {
    const user = userEvent.setup();
    render(<BasicModal />);
    await user.click(screen.getByText("Open"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ModalContent
// ---------------------------------------------------------------------------

describe("ModalContent", () => {
  it("renders the built-in close button by default", async () => {
    const user = userEvent.setup();
    render(<BasicModal />);
    await user.click(screen.getByText("Open"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Close")).toBeInTheDocument();
  });

  it("hides the close button when showCloseButton is false", async () => {
    const user = userEvent.setup();
    render(<BasicModal showCloseButton={false} />);
    await user.click(screen.getByText("Open"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).queryByLabelText("Close")).not.toBeInTheDocument();
  });

  it("merges custom className", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent className="custom-class">
          <ModalTitle>Title</ModalTitle>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByRole("dialog")).toHaveClass("custom-class");
  });

  it("applies data-slot attribute", async () => {
    const user = userEvent.setup();
    render(<BasicModal />);
    await user.click(screen.getByText("Open"));
    expect(screen.getByRole("dialog")).toHaveAttribute("data-slot", "modal-content");
  });
});

// ---------------------------------------------------------------------------
// ModalHeader / ModalFooter
// ---------------------------------------------------------------------------

describe("ModalHeader", () => {
  it("renders children", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalHeader>
            <ModalTitle>My header</ModalTitle>
          </ModalHeader>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByText("My header")).toBeInTheDocument();
  });

  it("applies data-slot attribute", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalHeader data-testid="header">
            <ModalTitle>Title</ModalTitle>
          </ModalHeader>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByTestId("header")).toHaveAttribute("data-slot", "modal-header");
  });

  it("merges custom className", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalHeader className="extra-class" data-testid="header">
            <ModalTitle>Title</ModalTitle>
          </ModalHeader>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByTestId("header")).toHaveClass("extra-class");
  });
});

describe("ModalFooter", () => {
  it("renders children", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalTitle>t</ModalTitle>
          <ModalFooter>
            <button type="button">Confirm</button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByText("Confirm")).toBeInTheDocument();
  });

  it("applies data-slot attribute", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalTitle>t</ModalTitle>
          <ModalFooter data-testid="footer">
            <button type="button">OK</button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByTestId("footer")).toHaveAttribute("data-slot", "modal-footer");
  });
});

// ---------------------------------------------------------------------------
// ModalTitle / ModalDescription
// ---------------------------------------------------------------------------

describe("ModalTitle", () => {
  it("renders content", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalTitle>My Title</ModalTitle>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByText("My Title")).toBeInTheDocument();
  });

  it("applies data-slot attribute", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalTitle data-testid="title">Title</ModalTitle>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByTestId("title")).toHaveAttribute("data-slot", "modal-title");
  });

  it("merges custom className", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalTitle data-testid="title" className="custom">
            Title
          </ModalTitle>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByTestId("title")).toHaveClass("custom");
  });
});

describe("ModalBody", () => {
  it("renders content", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalTitle>t</ModalTitle>
          <ModalBody>Some description</ModalBody>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByText("Some description")).toBeInTheDocument();
  });

  it("applies data-slot attribute", async () => {
    const user = userEvent.setup();
    render(
      <Modal>
        <ModalTrigger>Open</ModalTrigger>
        <ModalContent>
          <ModalTitle>t</ModalTitle>
          <ModalBody data-testid="desc">Description</ModalBody>
        </ModalContent>
      </Modal>
    );
    await user.click(screen.getByText("Open"));
    expect(screen.getByTestId("desc")).toHaveAttribute("data-slot", "modal-body");
  });
});
