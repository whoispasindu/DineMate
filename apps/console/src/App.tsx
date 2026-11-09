import { BUSINESS_ROLES, restoreSession, signOut, useStaffSession, type StaffUser } from "@dinemate/api-client";
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router";
import { Button } from "./kit";
import { ConsoleShell, navFor } from "./layout";
import { OverviewScreen } from "./screens/Overview";
import { OccupancyScreen } from "./screens/Occupancy";
import { PlannedScreen } from "./screens/Planned";
import { SafetyScreen } from "./screens/Safety";
import { SchedulesScreen } from "./screens/Schedules";
import { SeatsScreen } from "./screens/Seats";
import { ShopsScreen } from "./screens/Shops";
import { SignInScreen } from "./screens/SignIn";
import { TestVideosScreen } from "./screens/TestVideos";
import { ThresholdsScreen } from "./screens/Thresholds";
import { ZonesScreen } from "./screens/Zones";

const BUILT: Record<string, () => React.JSX.Element> = {
  "/shops": ShopsScreen,
  "/schedules": SchedulesScreen,
  "/zones": ZonesScreen,
  "/config": ThresholdsScreen,
  "/safety": SafetyScreen,
  "/occupancy": OccupancyScreen,
  "/seats": SeatsScreen,
  "/test-videos": TestVideosScreen,
};

function BusinessAccount() {
  return (
    <main id="main" className="flex min-h-dvh items-center justify-center bg-page px-4">
      <div className="raised flex w-full max-w-sm flex-col gap-3 rounded-[22px] border border-line bg-card p-7">
        <h1 className="m-0 font-display text-[28px] font-extrabold tracking-[-0.04em]">Business account</h1>
        <p className="m-0 text-sm text-muted">This account belongs to DineMate Business. Sign in on the business dashboard instead.</p>
        <Button tone="secondary" onClick={() => void signOut()}>
          Sign out
        </Button>
      </div>
    </main>
  );
}

function Home({ user }: { user: StaffUser }) {
  const first = navFor(user)[0];
  if (!first || first.to === "/") return <OverviewScreen />;
  return <Navigate to={first.to} replace />;
}

export function App() {
  const session = useStaffSession();
  useEffect(() => {
    void restoreSession();
  }, []);
  if (session.status === "unknown") return <div className="min-h-dvh bg-page" aria-busy="true" />;
  if (session.status === "signed_out") return <SignInScreen />;
  const user = session.user;
  if (BUSINESS_ROLES.includes(user.role)) return <BusinessAccount />;
  return (
    <Routes>
      <Route element={<ConsoleShell user={user} />}>
        <Route index element={<Home user={user} />} />
        {navFor(user)
          .filter((n) => n.to !== "/")
          .map((n) => {
            const Screen = BUILT[n.to] ?? PlannedScreen;
            return <Route key={n.to} path={n.to.slice(1)} element={<Screen />} />;
          })}
        <Route path="*" element={<PlannedScreen />} />
      </Route>
    </Routes>
  );
}
