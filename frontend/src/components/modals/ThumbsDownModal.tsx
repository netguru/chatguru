import { useState, useTransition } from "react";
import { Button } from "../ui/button";
import { Chip, ChipLabel } from "../ui/chip";
import { Modal, ModalBody, ModalContent, ModalFooter, ModalHeader, ModalTitle } from "../ui/modal";
import { Textarea } from "../ui/textarea";

const CHIPS = [
  "Incorrect or incomplete",
  "Not what I asked for",
  "Slow or buggy",
  "Style",
  "Safety or legal concern",
  "Other",
] as const;

interface ThumbsDownModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ThumbsDownModal({ open, onOpenChange }: ThumbsDownModalProps) {
  const [selectedChip, setSelectedChip] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [isPending, startTransition] = useTransition();

  function reset() {
    setSelectedChip(null);
    setText("");
  }

  function handleOpenChange(nextOpen: boolean) {
    onOpenChange(nextOpen);
    if (!nextOpen) reset();
  }

  function handleChipClick(label: string) {
    setSelectedChip(label);
    setText(label);
  }

  function handleSend() {
    startTransition(async () => {
      // TODO: call API endpoint
      console.log({ text });
      onOpenChange(false);
      reset();
    });
  }

  return (
    <Modal open={open} onOpenChange={handleOpenChange}>
      <ModalContent showCloseButton>
        <ModalHeader>
          <ModalTitle>How was your experience?</ModalTitle>
        </ModalHeader>
        <ModalBody className="flex flex-col gap-4 px-6 md:px-10">
          <div className="flex flex-wrap gap-x-2 gap-y-3">
            {CHIPS.map((label) => (
              <Chip
                key={label}
                aria-selected={selectedChip === label}
                onClick={() => handleChipClick(label)}
              >
                <ChipLabel>{label}</ChipLabel>
              </Chip>
            ))}
          </div>
          <Textarea
            placeholder="Tell us more (optional)"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="resize-none"
            rows={3}
          />
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" type="button" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSend} disabled={isPending || text.trim() === ""}>
            Send
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
