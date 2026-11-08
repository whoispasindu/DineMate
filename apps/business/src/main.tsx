import "@fontsource-variable/dm-sans";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource/jetbrains-mono/600.css";
import "./styles.css";
import { configureApi } from "@dinemate/api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./App";

configureApi({ baseUrl: import.meta.env.VITE_API_URL });

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, refetchIntervalInBackground: false } },
});

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}
