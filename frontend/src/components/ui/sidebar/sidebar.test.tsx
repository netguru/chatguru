import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
} from "./sidebar";

// jsdom doesn't implement window.matchMedia — provide a minimal stub
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

// Helper to render within a provider
function renderWithProvider(ui: React.ReactElement, options?: { defaultOpen?: boolean }) {
  return render(<SidebarProvider defaultOpen={options?.defaultOpen ?? true}>{ui}</SidebarProvider>);
}

// ----------------------------
// SidebarProvider + useSidebar
// ----------------------------

describe("SidebarProvider", () => {
  it("renders children", () => {
    render(
      <SidebarProvider>
        <div data-testid="child">content</div>
      </SidebarProvider>
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("exposes state via useSidebar", () => {
    function Consumer() {
      const { state } = useSidebar();
      return <span data-testid="state">{state}</span>;
    }
    render(
      <SidebarProvider defaultOpen>
        <Consumer />
      </SidebarProvider>
    );
    expect(screen.getByTestId("state")).toHaveTextContent("expanded");
  });

  it("reflects collapsed state when defaultOpen=false", () => {
    function Consumer() {
      const { state } = useSidebar();
      return <span data-testid="state">{state}</span>;
    }
    render(
      <SidebarProvider defaultOpen={false}>
        <Consumer />
      </SidebarProvider>
    );
    expect(screen.getByTestId("state")).toHaveTextContent("collapsed");
  });

  it("useSidebar throws outside provider", () => {
    const original = console.error;
    console.error = vi.fn();
    expect(() => render(<SidebarTrigger />)).toThrow(
      "useSidebar must be used within a SidebarProvider."
    );
    console.error = original;
  });
});

// --------------
// SidebarTrigger
// --------------

describe("SidebarTrigger", () => {
  it("renders a button", () => {
    renderWithProvider(<SidebarTrigger />);
    expect(screen.getByRole("button", { name: /toggle sidebar/i })).toBeInTheDocument();
  });

  it("toggles sidebar open/closed on click", async () => {
    const user = userEvent.setup();
    function Consumer() {
      const { state } = useSidebar();
      return (
        <>
          <SidebarTrigger />
          <span data-testid="state">{state}</span>
        </>
      );
    }
    renderWithProvider(<Consumer />);
    expect(screen.getByTestId("state")).toHaveTextContent("expanded");
    await user.click(screen.getByRole("button", { name: /toggle sidebar/i }));
    expect(screen.getByTestId("state")).toHaveTextContent("collapsed");
  });

  it("calls custom onClick handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithProvider(<SidebarTrigger onClick={onClick} />);
    await user.click(screen.getByRole("button", { name: /toggle sidebar/i }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

// --------------------------
// Sidebar (collapsible=none)
// --------------------------

describe("Sidebar collapsible=none", () => {
  it("renders a simple div with children", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <span data-testid="inner">inner</span>
      </Sidebar>
    );
    expect(screen.getByTestId("inner")).toBeInTheDocument();
  });
});

// -------------------------
// Structural sub-components
// -------------------------

describe("SidebarHeader", () => {
  it("renders children", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarHeader>
          <span data-testid="h">header</span>
        </SidebarHeader>
      </Sidebar>
    );
    expect(screen.getByTestId("h")).toBeInTheDocument();
  });

  it("has correct data-slot", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarHeader data-testid="header" />
      </Sidebar>
    );
    expect(screen.getByTestId("header")).toHaveAttribute("data-slot", "sidebar-header");
  });
});

describe("SidebarFooter", () => {
  it("renders children", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarFooter>
          <span data-testid="f">footer</span>
        </SidebarFooter>
      </Sidebar>
    );
    expect(screen.getByTestId("f")).toBeInTheDocument();
  });
});

describe("SidebarContent", () => {
  it("renders children", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarContent>
          <span data-testid="c">content</span>
        </SidebarContent>
      </Sidebar>
    );
    expect(screen.getByTestId("c")).toBeInTheDocument();
  });
});

describe("SidebarSeparator", () => {
  it("renders with role=separator", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarSeparator />
      </Sidebar>
    );
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });
});

describe("SidebarInset", () => {
  it("renders as main element", () => {
    renderWithProvider(<SidebarInset>main content</SidebarInset>);
    expect(screen.getByRole("main")).toHaveTextContent("main content");
  });
});

// ------------
// SidebarGroup
// ------------

describe("SidebarGroup + SidebarGroupLabel", () => {
  it("renders label text", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Projects</SidebarGroupLabel>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>
    );
    expect(screen.getByText("Projects")).toBeInTheDocument();
  });

  it("renders group action as button", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupAction aria-label="Add project">+</SidebarGroupAction>
            <SidebarGroupContent />
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>
    );
    expect(screen.getByRole("button", { name: /add project/i })).toBeInTheDocument();
  });
});

// -------------------------------
// SidebarMenu + SidebarMenuButton
// -------------------------------

describe("SidebarMenu", () => {
  it("renders as list", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton>Home</SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarContent>
      </Sidebar>
    );
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Home" })).toBeInTheDocument();
  });

  it("SidebarMenuButton isActive sets data-active", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton isActive data-testid="btn">
                Dashboard
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarContent>
      </Sidebar>
    );
    expect(screen.getByTestId("btn")).toHaveAttribute("data-active", "true");
  });

  it("SidebarMenuBadge renders badge text", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton>Inbox</SidebarMenuButton>
              <SidebarMenuBadge>12</SidebarMenuBadge>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarContent>
      </Sidebar>
    );
    expect(screen.getByText("12")).toBeInTheDocument();
  });
});

// --------------
// SidebarMenuSub
// --------------

describe("SidebarMenuSub", () => {
  it("renders sub items", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton>Parent</SidebarMenuButton>
              <SidebarMenuSub>
                <SidebarMenuSubItem>
                  <SidebarMenuSubButton href="/child">Child</SidebarMenuSubButton>
                </SidebarMenuSubItem>
              </SidebarMenuSub>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarContent>
      </Sidebar>
    );
    expect(screen.getByRole("link", { name: "Child" })).toBeInTheDocument();
  });

  it("SidebarMenuSubButton isActive sets data-active", () => {
    renderWithProvider(
      <Sidebar collapsible="none">
        <SidebarContent>
          <SidebarMenuSub>
            <SidebarMenuSubItem>
              <SidebarMenuSubButton isActive data-testid="sub-btn">
                Active
              </SidebarMenuSubButton>
            </SidebarMenuSubItem>
          </SidebarMenuSub>
        </SidebarContent>
      </Sidebar>
    );
    expect(screen.getByTestId("sub-btn")).toHaveAttribute("data-active", "true");
  });
});

// -----------------------
// Sidebar side prop
// -----------------------

describe("Sidebar side prop", () => {
  it("defaults to left side when SidebarProvider has no side prop", () => {
    const { container } = renderWithProvider(
      <Sidebar collapsible="offcanvas">
        <SidebarContent />
      </Sidebar>
    );
    const el = container.querySelector("[data-slot='sidebar']");
    expect(el).toHaveAttribute("data-side", "left");
  });

  it("renders with right side when Sidebar side='right'", () => {
    const { container } = renderWithProvider(
      <Sidebar side="right" collapsible="offcanvas">
        <SidebarContent />
      </Sidebar>
    );
    const el = container.querySelector("[data-slot='sidebar']");
    expect(el).toHaveAttribute("data-side", "right");
  });

  it("renders with left side when Sidebar side='left'", () => {
    const { container } = renderWithProvider(
      <Sidebar side="left" collapsible="offcanvas">
        <SidebarContent />
      </Sidebar>
    );
    const el = container.querySelector("[data-slot='sidebar']");
    expect(el).toHaveAttribute("data-side", "left");
  });

  it("Sidebar inherits side from SidebarProvider context", () => {
    const { container } = render(
      <SidebarProvider side="right">
        <Sidebar collapsible="offcanvas">
          <SidebarContent />
        </Sidebar>
      </SidebarProvider>
    );
    const el = container.querySelector("[data-slot='sidebar']");
    expect(el).toHaveAttribute("data-side", "right");
  });

  it("Sidebar side prop overrides SidebarProvider context", () => {
    const { container } = render(
      <SidebarProvider side="right">
        <Sidebar side="left" collapsible="offcanvas">
          <SidebarContent />
        </Sidebar>
      </SidebarProvider>
    );
    const el = container.querySelector("[data-slot='sidebar']");
    expect(el).toHaveAttribute("data-side", "left");
  });
});

// ----------------------------
// SidebarProvider side context
// ----------------------------

describe("SidebarProvider side context", () => {
  it("exposes side='left' by default", () => {
    function Consumer() {
      const { side } = useSidebar();
      return <span data-testid="side">{side}</span>;
    }
    render(
      <SidebarProvider>
        <Consumer />
      </SidebarProvider>
    );
    expect(screen.getByTestId("side")).toHaveTextContent("left");
  });

  it("exposes side='right' when configured", () => {
    function Consumer() {
      const { side } = useSidebar();
      return <span data-testid="side">{side}</span>;
    }
    render(
      <SidebarProvider side="right">
        <Consumer />
      </SidebarProvider>
    );
    expect(screen.getByTestId("side")).toHaveTextContent("right");
  });
});
