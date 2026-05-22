import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { loadThemePreference, resolveTheme } from "./styles/theme";

const initialPreference = loadThemePreference();
const initialSystemPrefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? true;
const initialTheme = resolveTheme(initialPreference, initialSystemPrefersDark);

document.documentElement.dataset.themePreference = initialPreference;
document.documentElement.dataset.theme = initialTheme;
document.documentElement.style.colorScheme = initialTheme === "dark" ? "dark" : "light";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
