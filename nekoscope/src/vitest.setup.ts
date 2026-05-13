import "@testing-library/jest-dom/vitest";

// react-flow needs ResizeObserver in jsdom
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

