import { restoreSession, useStaffSession, type StaffUser } from "@dinemate/api-client";
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router";
import { ConsoleShell, navFor } from "./layout";
import { OverviewScreen } from "./screens/Overview";
import { OccupancyScreen } from "./screens/Occupancy";
import { PlannedScreen } from "./screens/Planned";
import { SafetyScreen } from "./screens/Safety";
import { SchedulesScreen } from "./screens/Schedules";
import { SeatsScreen } from "./screens/Seats";
import { ShopsScreen } from "./screens/Shops";
import { SignInScreen } from "./screens/SignIn";
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
};

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
