import { LockSimpleIcon } from "@phosphor-icons/react";
import { Button } from "../ui/button";
import { Modal, ModalBody, ModalContent, ModalFooter } from "../ui/modal";

interface RequestAccessModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RequestAccessModal({ open, onOpenChange }: RequestAccessModalProps) {
  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent showCloseButton>
        <ModalBody className="pt-18 pb-14">
          <div className="p-6 flex flex-col items-center w-full">
            <LockSimpleIcon className="text-text-primary" weight="bold" size={32} />
            <h1 className="text-h3 font-strong text-text-primary tracking-s mt-3">
              You don't have permission to see this file.
            </h1>
            <p className="mt-1 text-t2 tracking-m text-text-secondary">
              You can request access below.
            </p>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" type="button" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button">Request access</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
