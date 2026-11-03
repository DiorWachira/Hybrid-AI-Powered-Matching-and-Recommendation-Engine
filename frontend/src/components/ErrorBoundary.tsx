import { Component, type ErrorInfo, type ReactNode } from "react";

const RELOAD_KEY = "jobbridge_chunk_reload";

// After a deployment, an open tab can ask for a page bundle that no longer exists.
function isStaleBundle(error: unknown) {
  return error instanceof Error && /dynamically imported module|Importing a module script failed|error loading dynamically imported/i.test(error.message);
}

function reloadOnce(): boolean {
  try {
    if (sessionStorage.getItem(RELOAD_KEY)) return false;
    sessionStorage.setItem(RELOAD_KEY, "1");
  } catch {
    return false;
  }
  window.location.reload();
  return true;
}

/** Keeps a page crash or an out-of-date bundle from leaving the visitor with a blank screen. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (isStaleBundle(error) && reloadOnce()) return;
    console.error("Page failed to render", error, info.componentStack);
  }

  componentDidMount() {
    try { sessionStorage.removeItem(RELOAD_KEY); } catch { /* storage unavailable */ }
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return <main className="auth-scene route-status" role="alert">
      <div className="route-status-card">
        <h1>This page could not load.</h1>
        <p>Your data is safe. Reload to try again; if that does not help, return to the home page.</p>
        <div className="route-status-actions"><button className="primary-button" onClick={() => window.location.reload()}>Reload</button><a className="secondary-button" href="/">Home</a></div>
      </div>
    </main>;
  }
}
