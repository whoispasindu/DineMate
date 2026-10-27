import { Link, Route, Routes } from "react-router";
import { MessageCard } from "./components/common";
import { AppShell } from "./components/shell";
import { AlertsScreen } from "./screens/Alerts";
import { CanteenScreen, CanteensIndex } from "./screens/Canteen";
import { FoodScreen } from "./screens/Food";
import { HomeScreen } from "./screens/Home";
import { MealsScreen } from "./screens/Meals";
import { WelcomeScreen } from "./screens/Welcome";

function NotFound() {
  return (
    <main id="main" className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 p-6">
      <MessageCard icon="question" title="Page not found" />
      <Link to="/" className="font-bold text-brand">
        Back to home
      </Link>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/welcome" element={<WelcomeScreen />} />
      <Route element={<AppShell />}>
        <Route index element={<HomeScreen />} />
        <Route path="canteens" element={<CanteensIndex />} />
        <Route path="canteens/:id" element={<CanteenScreen />} />
        <Route path="food" element={<FoodScreen />} />
        <Route path="meals" element={<MealsScreen />} />
        <Route path="alerts" element={<AlertsScreen />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
