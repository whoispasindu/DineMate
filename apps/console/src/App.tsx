import { Route, Routes } from "react-router";
import { ConsoleShell, NAV } from "./layout";
import { OverviewScreen } from "./screens/Overview";
import { PlannedScreen } from "./screens/Planned";

export function App() {
  return (
    <Routes>
      <Route element={<ConsoleShell />}>
        <Route index element={<OverviewScreen />} />
        {NAV.filter((n) => n.to !== "/").map((n) => (
          <Route key={n.to} path={n.to.slice(1)} element={<PlannedScreen />} />
        ))}
        <Route path="*" element={<PlannedScreen />} />
      </Route>
    </Routes>
  );
}
