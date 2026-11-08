import { BUSINESS_ROLES, restoreSession, signOut, useStaffSession } from "@dinemate/api-client";
import { useEffect } from "react";
import { Route, Routes } from "react-router";
import { Button } from "./kit";
import { BusinessShell } from "./layout";
import { CamerasScreen } from "./screens/Cameras";
import { CustomersScreen } from "./screens/Customers";
import { LiveFloorScreen } from "./screens/LiveFloor";
import { LaterScreen } from "./screens/Later";
import { ReportsScreen } from "./screens/Reports";
import { SettingsScreen } from "./screens/Settings";
import { SignInScreen } from "./screens/SignIn";
import { VenueProvider } from "./venue";

function CampusAccount() {
  return (
    <main id="main" className="flex min-h-dvh items-center justify-center bg-page px-4">
      <div className="raised flex w-full max-w-sm flex-col gap-3 rounded-[22px] border border-line bg-card p-7">
        <h1 className="m-0 font-display text-[28px] font-extrabold tracking-[-0.04em]">Campus account</h1>
        <p className="m-0 text-sm text-muted">This account belongs to the campus staff console. Sign in there instead.</p>
        <Button onClick={() => void signOut()}>Sign out</Button>
      </div>
    </main>
  );
}

export function App() {
  const session = useStaffSession();
  useEffect(() => {
    void restoreSession();
  }, []);
  if (session.status === "unknown") return <div className="min-h-dvh bg-page" aria-busy="true" />;
  if (session.status === "signed_out") return <SignInScreen />;
  const user = session.user;
  if (!BUSINESS_ROLES.includes(user.role)) return <CampusAccount />;
  return (
    <VenueProvider>
      <Routes>
        <Route element={<BusinessShell user={user} />}>
          <Route index element={<LiveFloorScreen />} />
          <Route path="customers" element={<CustomersScreen />} />
          <Route path="reports" element={<ReportsScreen />} />
          <Route path="cameras" element={<CamerasScreen />} />
          <Route path="settings" element={<SettingsScreen user={user} />} />
          <Route path="*" element={<LaterScreen />} />
        </Route>
      </Routes>
    </VenueProvider>
  );
}
