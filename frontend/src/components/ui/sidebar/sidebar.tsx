import { CaretDownIcon } from "@phosphor-icons/react/CaretDown";
import { SidebarSimpleIcon } from "@phosphor-icons/react/SidebarSimple";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { useIsMobile } from "../../../hooks/useIsMobile";
import { cn } from "../../../utils/utils";
import { IconButton, type IconButtonProps } from "../icon-button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "../sheet";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../tooltip";

/*
 * ---------
 * Constants
 * ---------
 */

const SIDEBAR_COOKIE_NAME = "silk_sidebar_state";
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7;

const SIDEBAR_WIDTH_ICON = "4.5rem";
const SIDEBAR_KEYBOARD_SHORTCUT = "b";

/*
 * -------
 * Context
 * -------
 */

type SidebarContextProps = {
  state: "expanded" | "collapsed";
  open: boolean;
  setOpen: (open: boolean) => void;
  openMobile: boolean;
  setOpenMobile: (open: boolean) => void;
  isMobile: boolean;
  toggleSidebar: () => void;
  side: "left" | "right";
};

const SidebarContext = React.createContext<SidebarContextProps | null>(null);

function useSidebar() {
  const context = React.useContext(SidebarContext);
  if (!context) throw new Error("useSidebar must be used within a SidebarProvider.");
  return context;
}

/*
 * ---------------
 * SidebarProvider
 * ---------------
 */

type SidebarProviderProps = React.ComponentProps<"div"> & {
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  side?: "left" | "right";
};

function SidebarProvider({
  defaultOpen = true,
  open: openProp,
  onOpenChange: setOpenProp,
  side = "left",
  className,
  style,
  children,
  ...props
}: SidebarProviderProps) {
  const isMobile = useIsMobile();
  const [openMobile, setOpenMobile] = React.useState(false);
  const [_open, _setOpen] = React.useState(defaultOpen);
  const open = openProp ?? _open;

  const setOpen = React.useCallback(
    (value: boolean | ((value: boolean) => boolean)) => {
      const openState = typeof value === "function" ? value(open) : value;
      if (setOpenProp) setOpenProp(openState);
      else _setOpen(openState);
      // biome-ignore lint/suspicious/noDocumentCookie: This is a deliberate use of cookies to persist the sidebar state across sessions.
      document.cookie = `${SIDEBAR_COOKIE_NAME}=${openState}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
    },
    [setOpenProp, open]
  );

  // When the sidebar is controlled (open prop provided) and on mobile, sync the
  // controlled value into openMobile so the mobile overlay branch stays in sync.
  React.useEffect(() => {
    if (isMobile && openProp !== undefined) {
      setOpenMobile(openProp);
    }
  }, [isMobile, openProp]);

  // Wrap setOpenMobile so that closing on mobile also notifies the controlled
  // onOpenChange callback (keeps external state like the store in sync).
  const handleSetOpenMobile = React.useCallback(
    (value: boolean) => {
      setOpenMobile(value);
      if (setOpenProp) setOpenProp(value);
    },
    [setOpenProp]
  );

  const toggleSidebar = React.useCallback(
    () => (isMobile ? handleSetOpenMobile(!openMobile) : setOpen((prev) => !prev)),
    [isMobile, openMobile, handleSetOpenMobile, setOpen]
  );

  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === SIDEBAR_KEYBOARD_SHORTCUT && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleSidebar]);

  const state = open ? "expanded" : "collapsed";

  const contextValue = React.useMemo<SidebarContextProps>(
    () => ({
      state,
      open,
      setOpen,
      isMobile,
      openMobile,
      setOpenMobile: handleSetOpenMobile,
      toggleSidebar,
      side,
    }),
    [state, open, setOpen, isMobile, openMobile, handleSetOpenMobile, toggleSidebar, side]
  );

  return (
    <TooltipProvider>
      <SidebarContext.Provider value={contextValue}>
        <div
          data-slot="sidebar-wrapper"
          style={{ "--sidebar-width-icon": SIDEBAR_WIDTH_ICON, ...style } as React.CSSProperties}
          className={cn(
            "group/sidebar-wrapper flex w-full [--sidebar-width:18rem] md:[--sidebar-width:12.5rem] lg:[--sidebar-width:16rem] has-data-[variant=inset]:bg-surface-neutral-soft",
            className
          )}
          {...props}
        >
          {children}
        </div>
      </SidebarContext.Provider>
    </TooltipProvider>
  );
}
SidebarProvider.displayName = "SidebarProvider";

/*
 * -------
 * Sidebar
 * -------
 */

type SidebarProps = React.ComponentProps<"div"> & {
  side?: "left" | "right";
  variant?: "sidebar" | "floating" | "inset";
  collapsible?: "offcanvas" | "icon" | "none";
};

function Sidebar({
  side: sideProp,
  variant = "sidebar",
  collapsible = "offcanvas",
  className,
  children,
  ...props
}: SidebarProps) {
  const { isMobile, state, openMobile, setOpenMobile, side: sideCtx } = useSidebar();
  const side = sideProp ?? sideCtx;

  if (collapsible === "none") {
    return (
      <div
        data-slot="sidebar"
        className={cn(
          "flex h-full w-(--sidebar-width) flex-col bg-surface-neutral-soft text-text-label",
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }

  if (isMobile) {
    return (
      <Sheet open={openMobile} onOpenChange={setOpenMobile}>
        <SheetContent side={side} className={cn("w-[18rem] p-0", className)} {...props}>
          {/* Required by Radix Dialog for accessibility — visually hidden but announced by screen readers. */}
          <SheetTitle className="sr-only">Sidebar</SheetTitle>
          <SheetDescription className="sr-only">Sidebar navigation</SheetDescription>
          <div
            data-slot="sidebar"
            data-sidebar="sidebar"
            data-slot-inner="sidebar-inner"
            data-mobile="true"
            className="flex h-full w-full flex-col"
          >
            {children}
          </div>
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <div
      className="group peer hidden text-text-label md:flex h-full shrink-0"
      data-state={state}
      data-collapsible={state === "collapsed" ? collapsible : ""}
      data-variant={variant}
      data-side={side}
      data-slot="sidebar"
    >
      <div
        data-slot="sidebar-container"
        data-side={side}
        className={cn(
          [
            /* Layout & Size */
            "flex h-full flex-col overflow-hidden",
            "w-(--sidebar-width)",
            /* Transition */
            "transition-[width] duration-200 ease-linear",
            /* Collapse */
            "group-data-[collapsible=offcanvas]:w-0",
          ],
          variant === "floating" || variant === "inset"
            ? [
                "p-2",
                "group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4))+2px)]",
              ]
            : [
                "group-data-[collapsible=icon]:w-(--sidebar-width-icon)",
                "group-data-[side=left]:border-r",
                "group-data-[side=right]:border-l",
              ],
          className
        )}
        {...props}
      >
        <div
          data-sidebar="sidebar"
          data-slot="sidebar-inner"
          className={cn([
            /* Background */
            "bg-surface-base",
            /* Layout & Size */
            "flex size-full flex-col min-w-(--sidebar-width) group-data-[collapsible=icon]:min-w-(--sidebar-width-icon)",
            /* Group variant */
            "group-data-[variant=floating]:rounded-lg",
            "group-data-[variant=floating]:shadow-sm",
            "group-data-[variant=floating]:ring-1",
            "group-data-[variant=floating]:ring-border-neutral-soft",
          ])}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
Sidebar.displayName = "Sidebar";

/*
 * --------------
 * SidebarTrigger
 * --------------
 */

type SidebarTriggerProps = Omit<IconButtonProps, "aria-label"> & {
  "aria-label"?: string;
};

function SidebarTrigger({ onClick, children, ...props }: SidebarTriggerProps) {
  const { toggleSidebar } = useSidebar();
  return (
    <IconButton
      data-sidebar="trigger"
      data-slot="sidebar-trigger"
      variant="tertiary"
      size="s"
      onClick={(event) => {
        onClick?.(event);
        toggleSidebar();
      }}
      aria-label={props["aria-label"] ?? "Toggle Sidebar"}
      {...props}
    >
      {children ?? <SidebarSimpleIcon />}
      <span className="sr-only">Toggle Sidebar</span>
    </IconButton>
  );
}
SidebarTrigger.displayName = "SidebarTrigger";

/*
 * -----------
 * SidebarRail
 * -----------
 */

function SidebarRail({ className, ...props }: React.ComponentProps<"button">) {
  const { toggleSidebar } = useSidebar();
  return (
    <button
      data-sidebar="rail"
      data-slot="sidebar-rail"
      aria-label="Toggle Sidebar"
      tabIndex={-1}
      onClick={toggleSidebar}
      title="Toggle Sidebar"
      className={cn(
        [
          /* Layout & Size */
          "absolute inset-y-0 z-20 hidden w-4 -translate-x-1/2",
          /* Transition */
          "transition-all ease-linear",
          /* Group side */
          "group-data-[side=left]:-right-4 group-data-[side=right]:left-0",
          /* After */
          "after:absolute after:inset-y-0 after:inset-s-1/2 after:w-0.5",
          /* Hover */
          "hover:after:bg-border-neutral-soft sm:flex",
          /* Cursor */
          "in-data-[side=left]:cursor-w-resize in-data-[side=right]:cursor-e-resize",
          "[[data-side=left][data-state=collapsed]_&]:cursor-e-resize",
          "[[data-side=right][data-state=collapsed]_&]:cursor-w-resize",
          /* Group in offcanvas mode */
          "group-data-[collapsible=offcanvas]:translate-x-0",
          "group-data-[collapsible=offcanvas]:after:left-full",
          /* Hover in offcanvas mode */
          "hover:group-data-[collapsible=offcanvas]:bg-surface-neutral-soft",
          /* Position in offcanvas mode */
          "[[data-side=left][data-collapsible=offcanvas]_&]:-right-2",
          "[[data-side=right][data-collapsible=offcanvas]_&]:-left-2",
        ],
        className
      )}
      {...props}
    />
  );
}
SidebarRail.displayName = "SidebarRail";

/*
 * ------------
 * SidebarInset
 * ------------
 */

function SidebarInset({ className, ...props }: React.ComponentProps<"main">) {
  return (
    <main
      data-slot="sidebar-inset"
      className={cn(
        [
          /* Layout & Size */
          "relative flex w-full flex-1 flex-col overflow-hidden",
          /* Group variant inset */
          "md:peer-data-[variant=inset]:m-2",
          "md:peer-data-[variant=inset]:ms-0",
          "md:peer-data-[variant=inset]:rounded-xl",
          "md:peer-data-[variant=inset]:peer-data-[state=collapsed]:ms-2",
        ],
        className
      )}
      {...props}
    />
  );
}
SidebarInset.displayName = "SidebarInset";

/*
 * -------------
 * SidebarHeader
 * -------------
 */

function SidebarHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-header"
      data-sidebar="header"
      className={cn("flex flex-col gap-2 p-2", className)}
      {...props}
    />
  );
}
SidebarHeader.displayName = "SidebarHeader";

/*
 * -------------
 * SidebarFooter
 * -------------
 */
function SidebarFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-footer"
      data-sidebar="footer"
      className={cn("flex flex-col gap-2 p-2", className)}
      {...props}
    />
  );
}
SidebarFooter.displayName = "SidebarFooter";

/*
 * ----------------
 * SidebarSeparator
 * ----------------
 */
function SidebarSeparator({ className, ...props }: React.ComponentProps<"div">) {
  return (
    // biome-ignore lint/a11y/useFocusableInteractive: This is a separator, not an interactive element.
    // biome-ignore lint/a11y/useSemanticElements: This is a separator, not a semantic element.
    <div
      // biome-ignore lint/a11y/useAriaPropsForRole: This is a separator, not an interactive element.
      role="separator"
      data-slot="sidebar-separator"
      data-sidebar="separator"
      className={cn(
        "mx-2 h-px w-auto bg-border-neutral-soft group-data-[collapsible=icon]:my-2",
        className
      )}
      {...props}
    />
  );
}
SidebarSeparator.displayName = "SidebarSeparator";

/*
 * --------------
 * SidebarContent
 * --------------
 */

function SidebarContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-content"
      data-sidebar="content"
      className={cn(
        [
          "flex min-h-0 flex-1 flex-col gap-0 overflow-auto p-2",
          "[&::-webkit-scrollbar]:hidden [scrollbar-width:none]",
          "group-data-[collapsible=icon]:overflow-hidden",
        ],
        className
      )}
      {...props}
    />
  );
}
SidebarContent.displayName = "SidebarContent";

/*
 * -------------------
 * SidebarGroupContext
 * -------------------
 */

type SidebarGroupContextProps = {
  open: boolean;
  toggleOpen: () => void;
  collapsible: boolean;
};

// eslint-disable-next-line @typescript-eslint/no-empty-function
const noop = () => {};

const SidebarGroupContext = React.createContext<SidebarGroupContextProps>({
  open: true,
  toggleOpen: noop,
  collapsible: false,
});

/*
 * ------------
 * SidebarGroup
 * ------------
 */
type SidebarGroupProps = React.ComponentProps<"div"> & {
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

function SidebarGroup({
  defaultOpen,
  open: openProp,
  onOpenChange,
  className,
  children,
  ...props
}: SidebarGroupProps) {
  const collapsible = defaultOpen !== undefined || openProp !== undefined;
  const [_open, _setOpen] = React.useState(defaultOpen ?? true);
  const open = openProp !== undefined ? openProp : _open;

  const toggleOpen = React.useCallback(() => {
    const next = !open;
    if (openProp === undefined) _setOpen(next);
    onOpenChange?.(next);
  }, [open, openProp, onOpenChange]);

  return (
    <SidebarGroupContext.Provider value={{ open, toggleOpen, collapsible }}>
      <div
        data-slot="sidebar-group"
        data-sidebar="group"
        className={cn("relative flex w-full min-w-0 flex-col", className)}
        {...props}
      >
        {children}
      </div>
    </SidebarGroupContext.Provider>
  );
}
SidebarGroup.displayName = "SidebarGroup";

/*
 * -----------------
 * SidebarGroupLabel
 * -----------------
 */

type SidebarGroupLabelProps = React.ComponentProps<"div"> & {
  asChild?: boolean;
};

function SidebarGroupLabel({ className, asChild = false, ...props }: SidebarGroupLabelProps) {
  const Comp = asChild ? Slot : "div";
  return (
    <Comp
      data-slot="sidebar-group-label"
      data-sidebar="group-label"
      className={cn(
        [
          /* Text */
          "text-t5 font-strong text-text-tertiary",
          /* Layout & Size */
          "flex h-8 w-full shrink-0 items-center px-2 outline-hidden mb-1",
          /* Focus visible */
          "focus-visible:ring",
          /* Transition */
          "transition-[height,opacity] duration-200 ease-linear",
          /* Group collapsible icon */
          "group-data-[collapsible=icon]:h-0 group-data-[collapsible=icon]:overflow-hidden group-data-[collapsible=icon]:opacity-0",
          /* Children */
          "[&>svg]:size-4 [&>svg]:shrink-0",
        ],
        className
      )}
      {...props}
    />
  );
}
SidebarGroupLabel.displayName = "SidebarGroupLabel";

/*
 * ------------------
 * SidebarGroupAction
 * ------------------
 */
type SidebarGroupActionProps = React.ComponentProps<"button"> & {
  asChild?: boolean;
};

function SidebarGroupAction({
  className,
  asChild = false,
  onClick,
  children,
  ...props
}: SidebarGroupActionProps) {
  const { open, toggleOpen, collapsible } = React.useContext(SidebarGroupContext);
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      data-slot="sidebar-group-action"
      data-sidebar="group-action"
      onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
        if (collapsible) toggleOpen();
        onClick?.(e);
      }}
      className={cn(
        [
          /* Background */
          "bg-transparent",
          "hover:bg-surface-hover-interactive-strong/10",
          "active:bg-surface-active-interactive-strong/20",
          /* Layout & Size */
          "ml-auto shrink-0 inline-flex items-center justify-center",
          "size-6 p-1 rounded-m",
          /* Interaction */
          "cursor-pointer transition-colors",
          /* Focus visible */
          "focus-visible:outline-hidden focus-visible:ring",
          /* Disabled */
          "disabled:pointer-events-none disabled:text-text-disabled-interactive",
          /* Group collapsible icon */
          "group-data-[collapsible=icon]:hidden",
          /* Children */
          "[&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:pointer-events-none",
        ],
        className
      )}
      {...props}
    >
      {collapsible ? (
        <CaretDownIcon
          weight="bold"
          className={cn("transition-transform duration-200 ease-in-out", open && "rotate-180")}
        />
      ) : (
        children
      )}
    </Comp>
  );
}
SidebarGroupAction.displayName = "SidebarGroupAction";

/*
 * -------------------
 * SidebarGroupContent
 * -------------------
 */
function SidebarGroupContent({ className, ...props }: React.ComponentProps<"div">) {
  const { open, collapsible } = React.useContext(SidebarGroupContext);
  return (
    <div
      className={cn(
        "grid",
        collapsible
          ? [
              "transition-[grid-template-rows] duration-200 ease-in-out",
              open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
            ]
          : "grid-rows-[1fr]"
      )}
    >
      <div
        data-slot="sidebar-group-content"
        data-sidebar="group-content"
        className={cn("w-full overflow-hidden text-sm", className)}
        {...props}
      />
    </div>
  );
}
SidebarGroupContent.displayName = "SidebarGroupContent";

/*
 * ----------------------
 * SidebarMenuItemContext
 * ----------------------
 */

type SidebarMenuItemContextProps = {
  open: boolean;
  toggleOpen: () => void;
  collapsible: boolean;
  registerSub: () => void;
  unregisterSub: () => void;
};

const SidebarMenuItemContext = React.createContext<SidebarMenuItemContextProps>({
  open: true,
  toggleOpen: noop,
  collapsible: false,
  registerSub: noop,
  unregisterSub: noop,
});

/*
 * -----------
 * SidebarMenu
 * -----------
 */

function SidebarMenu({ className, ...props }: React.ComponentProps<"ul">) {
  return (
    <ul
      data-slot="sidebar-menu"
      data-sidebar="menu"
      className={cn("flex w-full min-w-0 flex-col gap-2", className)}
      {...props}
    />
  );
}
SidebarMenu.displayName = "SidebarMenu";

/*
 * ---------------
 * SidebarMenuItem
 * ---------------
 */
type SidebarMenuItemProps = React.ComponentProps<"li"> & {
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

function SidebarMenuItem({
  defaultOpen,
  open: openProp,
  onOpenChange,
  className,
  children,
  ...props
}: SidebarMenuItemProps) {
  const [hasSub, setHasSub] = React.useState(false);
  const collapsible = hasSub || defaultOpen !== undefined || openProp !== undefined;
  const [_open, _setOpen] = React.useState(defaultOpen ?? true);
  const open = openProp !== undefined ? openProp : _open;

  const registerSub = React.useCallback(() => setHasSub(true), []);
  const unregisterSub = React.useCallback(() => setHasSub(false), []);

  const toggleOpen = React.useCallback(() => {
    const next = !open;
    if (openProp === undefined) _setOpen(next);
    onOpenChange?.(next);
  }, [open, openProp, onOpenChange]);

  return (
    <SidebarMenuItemContext.Provider
      value={{ open, toggleOpen, collapsible, registerSub, unregisterSub }}
    >
      <li
        data-slot="sidebar-menu-item"
        data-sidebar="menu-item"
        className={cn(
          "group/menu-item relative flex flex-col gap-2 group-data-[collapsible=icon]:items-center",
          className
        )}
        {...props}
      >
        {children}
      </li>
    </SidebarMenuItemContext.Provider>
  );
}
SidebarMenuItem.displayName = "SidebarMenuItem";

/*
 * -----------------
 * SidebarMenuButton
 * -----------------
 */

const sidebarMenuButtonVariants = cva([
  "peer/menu-button group/menu-button",
  /* Background */
  "bg-surface-base",
  "hover:bg-surface-hover-base",
  "data-[active=true]:bg-surface-hover-base",
  "active:bg-surface-active-base focus-visible:bg-surface-active-base",
  "data-[active=true]:active:bg-surface-active-base",
  /* Text */
  "text-left text-t3 text-text-label",
  /* Border */
  "rounded-m outline-hidden",
  /* Size */
  "w-full h-11 py-2 ps-3 pe-4",
  /* Layout */
  "flex items-center gap-2 overflow-hidden",
  /* Focus visible */
  "focus-visible:ring",
  /* Transition */
  "transition-[width,height,padding]",
  /* Group */
  "group-has-data-[sidebar=menu-action]/menu-item:pe-8",
  "group-data-[collapsible=icon]:data-[active=true]:border group-data-[collapsible=icon]:data-[active=true]:border-border-neutral-soft",
  "group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:p-2!",
  /* Disabled */
  "disabled:pointer-events-none disabled:opacity-50",
  "aria-disabled:pointer-events-none aria-disabled:opacity-50",
  /* Children */
  "[&_svg]:size-4 [&_svg]:shrink-0 [&>span]:truncate",
]);

type SidebarMenuButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof sidebarMenuButtonVariants> & {
    asChild?: boolean;
    isActive?: boolean;
    /** Tooltip shown in icon-collapsed mode. Pass a string or TooltipContent props. */
    tooltip?: string | React.ComponentProps<typeof TooltipContent>;
  };

function SidebarMenuButton({
  asChild = false,
  isActive = false,
  tooltip,
  className,
  onClick,
  children,
  ...props
}: SidebarMenuButtonProps) {
  const { open, toggleOpen, collapsible } = React.useContext(SidebarMenuItemContext);
  const { isMobile, state } = useSidebar();
  const Comp = asChild ? Slot : "button";

  const buttonProps = {
    "data-slot": "sidebar-menu-button",
    "data-sidebar": "menu-button",
    "data-active": isActive,
    className: cn(sidebarMenuButtonVariants(), className),
    onClick: (e: React.MouseEvent<HTMLButtonElement>) => {
      if (collapsible) toggleOpen();
      onClick?.(e);
    },
    ...props,
  };

  const button = asChild ? (
    <Comp {...buttonProps}>{children}</Comp>
  ) : (
    <Comp {...buttonProps}>
      {children}
      {collapsible && (
        <CaretDownIcon
          weight="bold"
          className={cn(
            "ml-auto shrink-0 transition-transform duration-200 ease-in-out group-data-[collapsible=icon]:hidden",
            open && "rotate-180"
          )}
        />
      )}
    </Comp>
  );

  if (!tooltip) return button;

  const tooltipProps: React.ComponentProps<typeof TooltipContent> =
    typeof tooltip === "string" ? { children: tooltip } : tooltip;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent
        side="right"
        align="center"
        hidden={state !== "collapsed" || isMobile}
        {...tooltipProps}
      />
    </Tooltip>
  );
}
SidebarMenuButton.displayName = "SidebarMenuButton";

/*
 * ----------------
 * SidebarMenuBadge
 * ----------------
 */

function SidebarMenuBadge({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-menu-badge"
      data-sidebar="menu-badge"
      className={cn(
        [
          /* Background */
          "bg-surface-interactive-medium",
          /* Text */
          "text-text-interactive text-t4 leading-l font-soft tabular-nums",
          /* Size */
          "h-5 min-w-5 px-1",
          /* Layout */
          "shrink-0 pointer-events-none flex items-center justify-center select-none",
          /* Border */
          "rounded-full",
          /* Group active */
          "group-active/menu-button:bg-surface-interactive-strong group-active/menu-button:text-text-inverted",
          /* Group focus visible */
          "group-focus-visible/menu-button:bg-surface-interactive-strong group-focus-visible/menu-button:text-text-inverted",
          /* Hidden in icon-only mode (button has overflow-hidden, badge can't escape) */
          "group-data-[collapsible=icon]:absolute",
          "group-data-[collapsible=icon]:top-0",
          "group-data-[collapsible=icon]:right-0",
        ],
        className
      )}
      {...props}
    />
  );
}
SidebarMenuBadge.displayName = "SidebarMenuBadge";

/*
 * --------------
 * SidebarMenuSub
 * --------------
 */

function SidebarMenuSub({ className, ...props }: React.ComponentProps<"ul">) {
  const { open, collapsible, registerSub, unregisterSub } =
    React.useContext(SidebarMenuItemContext);

  React.useEffect(() => {
    registerSub();
    return () => unregisterSub();
  }, [registerSub, unregisterSub]);

  return (
    <div
      className={cn(
        "grid group-data-[collapsible=icon]:hidden",
        collapsible
          ? [
              "transition-[grid-template-rows] duration-200 ease-in-out",
              open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
            ]
          : "grid-rows-[1fr]"
      )}
    >
      <ul
        data-slot="sidebar-menu-sub"
        data-sidebar="menu-sub"
        className={cn(
          ["pl-6 flex min-w-0 translate-x-px flex-col gap-2 overflow-hidden"],
          className
        )}
        {...props}
      />
    </div>
  );
}
SidebarMenuSub.displayName = "SidebarMenuSub";

/*
 * ------------------
 * SidebarMenuSubItem
 * ------------------
 */
function SidebarMenuSubItem({ className, ...props }: React.ComponentProps<"li">) {
  return (
    <li
      data-slot="sidebar-menu-sub-item"
      data-sidebar="menu-sub-item"
      className={cn("group/menu-sub-item relative", className)}
      {...props}
    />
  );
}
SidebarMenuSubItem.displayName = "SidebarMenuSubItem";

type SidebarMenuSubButtonProps = React.ComponentProps<"a"> & {
  asChild?: boolean;
  size?: "sm" | "md";
  isActive?: boolean;
};

/*
 * --------------------
 * SidebarMenuSubButton
 * --------------------
 */
function SidebarMenuSubButton({
  asChild = false,
  size = "md",
  isActive = false,
  className,
  ...props
}: SidebarMenuSubButtonProps) {
  const Comp = asChild ? Slot : "a";
  return (
    <Comp
      data-slot="sidebar-menu-sub-button"
      data-sidebar="menu-sub-button"
      data-size={size}
      data-active={isActive}
      className={cn(
        [
          /* Background */
          "bg-surface-base",
          "hover:bg-surface-interactive-medium",
          "data-[active=true]:bg-surface-interactive-soft",
          "active:bg-surface-active-base focus-visible:bg-surface-active-base",
          /* Text */
          "text-t3 text-text-label",
          /* Border */
          "rounded-m",
          /* Layout & Size */
          "flex h-11 min-w-0 -translate-x-px items-center gap-2 overflow-hidden outline-hidden",
          "py-2 ps-3 pe-4",
          /* Focus visible */
          "focus-visible:ring",
          /* Cursor */
          "cursor-pointer",
          /* Group collapsible */
          "group-data-[collapsible=icon]:hidden",
          /* Disabled */
          "disabled:pointer-events-none disabled:opacity-50",
          "aria-disabled:pointer-events-none aria-disabled:opacity-50",
          /* Children */
          "[&>span]:truncate [&>svg]:size-4 [&>svg]:shrink-0",
        ],
        className
      )}
      {...props}
    />
  );
}
SidebarMenuSubButton.displayName = "SidebarMenuSubButton";

/*
 * -------
 * Exports
 * -------
 */

export type {
  SidebarGroupActionProps,
  SidebarGroupLabelProps,
  SidebarGroupProps,
  SidebarMenuButtonProps,
  SidebarMenuItemProps,
  SidebarMenuSubButtonProps,
  SidebarProps,
  SidebarProviderProps,
  SidebarTriggerProps,
};
export {
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
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
  sidebarMenuButtonVariants,
  useSidebar,
};
