import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./router";
import { ToastProvider } from "./components/ui/Toast";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>
);
