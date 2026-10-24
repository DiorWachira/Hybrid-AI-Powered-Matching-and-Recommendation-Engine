import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

type GoogleIdentity = {
  accounts: { id: {
    initialize: (options: { client_id: string; callback: (response: { credential: string }) => void; ux_mode: "popup"; auto_select: boolean }) => void;
    renderButton: (parent: HTMLElement, options: Record<string, string | number>) => void;
  } };
};
declare global { interface Window { google?: GoogleIdentity } }

const SCRIPT_URL = "https://accounts.google.com/gsi/client";
let scriptLoad: Promise<void> | null = null;
// Google only accepts registered origins, and those use the localhost name, not the loopback address.
const LOOPBACK_IPS = new Set(["127.0.0.1", "[::1]"]);

function loadGoogleScript(): Promise<void> {
  scriptLoad ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_URL; script.async = true;
    script.onload = () => resolve();
    script.onerror = () => { scriptLoad = null; reject(new Error("Google sign-in could not load")); };
    document.head.appendChild(script);
  });
  return scriptLoad;
}

/** "Sign in with Google" for enabled accounts. Renders nothing while the server has it switched off or Google cannot load. */
export function GoogleSignIn({ disabled, onCredential }: { disabled: boolean; onCredential: (credential: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  callback.current = onCredential;
  const [ready, setReady] = useState(false);
  const [localhostUrl, setLocalhostUrl] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    void api.googleSignInOptions()
      .then(async ({ client_id }) => {
        if (!client_id) return;
        if (LOOPBACK_IPS.has(window.location.hostname)) {
          const url = new URL(window.location.href);
          url.hostname = "localhost";
          if (active) setLocalhostUrl(url.toString());
          return;
        }
        await loadGoogleScript();
        if (!active || !container.current || !window.google) return;
        window.google.accounts.id.initialize({ client_id, callback: (response) => callback.current(response.credential), ux_mode: "popup", auto_select: false });
        window.google.accounts.id.renderButton(container.current, { type: "standard", theme: "filled_black", size: "large", text: "signin_with", shape: "rectangular", width: 320 });
        setReady(true);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);
  if (localhostUrl) return <div className="google-signin">
    <span className="google-signin-divider">or</span>
    <p className="google-signin-note">Sign in with Google works at <a href={localhostUrl}>localhost</a>. You will need to sign in again there.</p>
  </div>;
  return <div className="google-signin" hidden={!ready} aria-disabled={disabled}>
    <span className="google-signin-divider">or</span>
    <div ref={container} style={disabled ? { pointerEvents: "none", opacity: 0.6 } : undefined} />
  </div>;
}
