import { useActionState, useRef, useState } from "react";
import { Button } from "../ui/button";
import { Modal, ModalBody, ModalContent, ModalFooter, ModalHeader, ModalTitle } from "../ui/modal";
import { Rating, RatingStars, RatingTitle } from "../ui/rating";
import { Textarea } from "../ui/textarea";

interface FeedbackModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function FeedbackModal({ open, onOpenChange }: FeedbackModalProps) {
  const [rating, setRating] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);

  function reset() {
    setRating(0);
    formRef.current?.reset();
  }

  async function submitFeedback(_prevState: unknown, formData: FormData) {
    const ratingValue = Number(formData.get("rating"));
    const text = formData.get("text") as string;
    // TODO: call API endpoint
    console.log({ rating: ratingValue, text });
    onOpenChange(false);
    reset();
    return null;
  }

  const [, formAction, isPending] = useActionState(submitFeedback, null);

  function handleOpenChange(nextOpen: boolean) {
    onOpenChange(nextOpen);
    if (!nextOpen) reset();
  }

  return (
    <Modal open={open} onOpenChange={handleOpenChange}>
      <ModalContent showCloseButton>
        <ModalHeader>
          <ModalTitle>Share feedback</ModalTitle>
        </ModalHeader>
        <form ref={formRef} action={formAction}>
          <ModalBody className="flex flex-col items-center gap-6 text-left px-6 md:px-10">
            <input type="hidden" name="rating" value={rating} />
            <Rating value={rating} onValueChange={setRating}>
              <RatingTitle />
              <RatingStars />
            </Rating>
            <Textarea
              name="text"
              placeholder="Tell us about your experience (optional)"
              className="resize-none"
              rows={3}
            />
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" type="button" onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || rating === 0}>
              Send
            </Button>
          </ModalFooter>
        </form>
      </ModalContent>
    </Modal>
  );
}
