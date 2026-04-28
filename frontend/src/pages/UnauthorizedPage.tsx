import { Logo } from "../components/branding/logo";
import { Button } from "../components/ui/button";
import { useAuth } from "../hooks/useAuth";

export function UnauthorizedPage() {
  const { login } = useAuth();

  return (
    <div className="h-screen bg-surface-base grid place-items-center px-5">
      <div className="bg-surface-neutral-soft rounded-l flex flex-col items-center justify-center py-14 px-6 w-fit">
        <Logo className="h-14" />
        <h1 className="text-h3 font-strong text-text-secondary text-center mt-6 tracking-s">
          You don't have permission to visit Chatguru.
        </h1>
        <p className="text-t2 text-text-secondary font-soft tracking-m">
          You can request access below.
        </p>
        <Button variant="fill" size="m" className="mt-8" onClick={() => login("test")}>
          Request access
        </Button>
      </div>
    </div>
  );
}
