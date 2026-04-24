import { Link, useLocation } from "react-router-dom";
import { Logo } from "../components/branding/logo";
import { SidebarTrigger } from "../components/ui/sidebar/sidebar";
import { selectCurrentSession, useAppStore } from "../store/appStore";

export function Header() {
  const currentSession = useAppStore(selectCurrentSession);
  const { pathname } = useLocation();

  return (
    <div className="h-14 w-full grid grid-cols-[1fr_auto_1fr] px-4 md:px-8 items-center gap-3 bg-surface-base border-b border-border-neutral-soft">
      <div className="flex items-center gap-3">
        <SidebarTrigger />
        <h1 className="text-lg font-semibold text-text-title">
          <Link to="/" aria-label="Go to chat">
            <Logo className="h-4" />
          </Link>
          <span className="sr-only">ChatGuru logo</span>
        </h1>
      </div>

      {currentSession && pathname === "/" && (
        <p className="text-t3 font-strong text-text-primary text-center truncate max-w-xs md:max-w-sm">
          {currentSession.title}
        </p>
      )}

      <div />
    </div>
  );
}
