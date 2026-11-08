import { apiMode, signIn } from "@dinemate/api-client";
import { APP_NAME, BrandMark } from "@dinemate/ui";
import { useState, type FormEvent } from "react";
import { Banner, Button, errorText, Field, TextInput } from "../kit";

export function SignInScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const sample = apiMode() === "sample";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <main id="main" className="flex min-h-dvh items-center justify-center bg-page px-4">
      <form
        onSubmit={(e) => void submit(e)}
        className="raised flex w-full max-w-sm flex-col gap-4 rounded-[22px] border border-line bg-card p-7"
      >
        <div className="flex items-center gap-2.5">
          <BrandMark size={36} />
          <span className="flex flex-col">
            <span className="font-display text-[19px] font-extrabold tracking-[-0.02em]">{APP_NAME}</span>
            <span className="text-xs text-muted">Staff console</span>
          </span>
        </div>
        <h1 className="m-0 font-display text-[32px] font-extrabold tracking-[-0.04em]">Sign in</h1>
        {sample ? (
          <Banner>Sample data mode: sign in as admin@, canteen.a@, rice.stall@ or safety@dinemate.test with any password.</Banner>
        ) : null}
        {error ? <Banner tone="error">{error}</Banner> : null}
        <Field label="Email">
          <TextInput type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password">
          <TextInput
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Button tone="primary" type="submit" disabled={busy} className="min-h-11">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
        <p className="m-0 text-xs text-muted">Accounts are created by the campus administrator.</p>
      </form>
    </main>
  );
}
