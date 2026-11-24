import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./tailwind.css";
import "./styles.css";

// Clerk sign-in (auth.jsx) only when web/.env sets VITE_CLERK_PUBLISHABLE_KEY; loaded
// separately, so the app doesn't ship Clerk's code when sign-in is off.
const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
const WithSignIn = CLERK_KEY ? lazy(() => import("./auth.jsx")) : null;

createRoot(document.getElementById("root")).render(
  <StrictMode>
    {WithSignIn ? (
      <Suspense fallback={null}>
        <WithSignIn publishableKey={CLERK_KEY}>
          <App />
        </WithSignIn>
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
);
