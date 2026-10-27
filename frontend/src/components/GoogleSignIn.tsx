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
// Google renders its button between 200 and 400 px wide; match the form column inside that range.
const clampWidth = (width: number) => Math.round(Math.min(400, Math.max(200, width)));
let scriptLoad: Promise<void> | null = null;

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
  useEffect(() => {
    let active = true;
    void api.googleSignInOptions()
      .then(async ({ client_id }) => {
        if (!client_id) return;
        await loadGoogleScript();
        if (!active || !container.current || !window.google) return;
        window.google.accounts.id.initialize({ client_id, callback: (response) => callback.current(response.credential), ux_mode: "popup", auto_select: false });
        setReady(true);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);
  // Render once the wrapper is visible, and again whenever the form column changes width.
  useEffect(() => {
    const target = container.current;
    if (!ready || !target || !window.google) return;
    let renderedWidth = 0;
    const render = () => {
      const width = clampWidth(target.clientWidth);
      if (!window.google || width === renderedWidth) return;
      renderedWidth = width;
      window.google.accounts.id.renderButton(target, { type: "standard", theme: "filled_black", size: "large", text: "signin_with", shape: "rectangular", logo_alignment: "center", width });
    };
    render();
    const observer = new ResizeObserver(render);
    observer.observe(target);
    return () => observer.disconnect();
  }, [ready]);
  return <div className="google-signin" hidden={!ready} aria-disabled={disabled}>
    <span className="google-signin-divider">or</span>
    <div ref={container} className="google-signin-button" style={disabled ? { pointerEvents: "none", opacity: 0.6 } : undefined} />
  </div>;
}
