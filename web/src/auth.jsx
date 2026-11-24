import { ClerkProvider, Show, SignIn, UserButton, useAuth } from "@clerk/react";
import { setTokenGetter } from "./api.js";

/** Sign-in with Clerk around the app (WHATS_LEFT 3.4): signed-out visitors see Clerk's
 * sign-in, signed-in users see the app with their account button, and every request
 * carries their session token. */
export default function WithSignIn({ publishableKey, children }) {
  return (
    <ClerkProvider publishableKey={publishableKey}>
      <Show when="signed-out">
        <main className="sign-in-page">
          <SignIn routing="hash" />
        </main>
      </Show>
      <Show when="signed-in">
        <SessionToken />
        <div className="account-button">
          <UserButton />
        </div>
        {children}
      </Show>
    </ClerkProvider>
  );
}

/** Hands Clerk's getToken to api.js. Set while rendering, so it's there before any question
 * is sent; getToken returns a fresh token each time (Clerk's last for about a minute). */
function SessionToken() {
  const { getToken } = useAuth();
  setTokenGetter(getToken);
  return null;
}
