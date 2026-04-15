import "@testing-library/jest-dom";

// jsdom does not implement ResizeObserver — required by Radix UI Popper
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
