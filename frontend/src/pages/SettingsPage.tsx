import type { ReactNode } from "react";
import { Button } from "../components/ui/button";
import { Container } from "../components/ui/container";
import { Textarea } from "../components/ui/textarea";
import { useAuth } from "../hooks/useAuth";

interface SettingsRowProps {
  label: string;
  children: ReactNode;
}

function SettingsRow({ label, children }: SettingsRowProps) {
  return (
    <div className="flex items-center justify-between gap-6 py-4">
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-t2 font-medium text-text-secondary">{label}</span>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

interface SettingsSectionProps {
  title: string;
  children: ReactNode;
}

function SettingsSection({ title, children }: SettingsSectionProps) {
  return (
    <section className="mt-8">
      <h2 className="text-h5 font-strong text-text-primary pb-3 border-b border-border-neutral-soft">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function SettingsPage() {
  const { logout } = useAuth();

  return (
    <div className="flex-1 overflow-y-auto">
      <Container>
        <h1 className="text-h3 font-strong mb-4 pb-4 text-text-primary border-b border-border-neutral-soft">
          Settings
        </h1>

        <SettingsRow label="Signed in">
          <Button variant="outline" onClick={logout}>
            Sign out
          </Button>
        </SettingsRow>
        <SettingsRow label="Preferred response language">
          <Button variant="outline">English</Button>
        </SettingsRow>
        <SettingsRow label="Include citations">
          <Button variant="outline">Enabled</Button>
        </SettingsRow>

        <SettingsSection title="Preferences">
          <SettingsRow label="Preferred tone & style">
            <Button variant="outline">Neutral</Button>
          </SettingsRow>
          <div className="py-4 flex flex-col gap-3">
            <div className="flex flex-col gap-0.5">
              <span className="text-t2 font-medium text-text-secondary">Personalization</span>
            </div>
            <Textarea
              placeholder="E.g. I'm a biomedical engineer focused on regulatory compliance..."
              className="resize-none"
              rows={4}
            />
          </div>
        </SettingsSection>

        <div className="pb-10" />
      </Container>
    </div>
  );
}
