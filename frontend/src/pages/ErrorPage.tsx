import { isRouteErrorResponse, useRouteError } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Logo } from "../components/ui/icons/logo";

export function ErrorPage() {
  const error = useRouteError();

  const { title, description } = resolveError(error);

  function handleGoHome() {
    window.location.replace("/");
  }

  return (
    <div className="h-screen bg-surface-base grid place-items-center px-5">
      <div className="bg-surface-neutral-soft rounded-l flex flex-col items-center justify-center py-14 px-6 w-fit max-w-sm">
        <Logo className="h-14" />
        <h1 className="text-h3 font-strong text-text-secondary text-center mt-6 tracking-s">
          {title}
        </h1>
        <p className="text-t2 text-text-secondary font-soft tracking-m text-center mt-2">
          {description}
        </p>
        <Button variant="fill" size="m" className="mt-8" onClick={handleGoHome}>
          Go to home
        </Button>
      </div>
    </div>
  );
}

function resolveError(error: unknown): { title: string; description: string } {
  if (isRouteErrorResponse(error)) {
    if (error.status === 404) {
      return {
        title: "Page not found.",
        description: "The page you're looking for doesn't exist.",
      };
    }
    return {
      title: "Something went wrong.",
      description: error.statusText || `Error ${error.status}`,
    };
  }

  if (error instanceof Error) {
    return {
      title: "Something went wrong.",
      description: error.message,
    };
  }

  return {
    title: "Something went wrong.",
    description: "An unexpected error occurred. Please try again.",
  };
}
