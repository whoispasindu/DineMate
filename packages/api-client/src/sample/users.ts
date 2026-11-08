import type { StaffUser } from "../types";

export const SAMPLE_USERS: StaffUser[] = [
  {
    id: "sample-admin",
    email: "admin@dinemate.test",
    display_name: "Campus administrator",
    role: "campus_admin",
    canteen_ids: [],
    shop_ids: [],
  },
  {
    id: "sample-canteen-a",
    email: "canteen.a@dinemate.test",
    display_name: "Canteen A manager",
    role: "canteen_manager",
    canteen_ids: ["a"],
    shop_ids: [],
  },
  {
    id: "sample-rice",
    email: "rice.stall@dinemate.test",
    display_name: "Rice & Curry Stall manager",
    role: "shop_manager",
    canteen_ids: [],
    shop_ids: ["s-rice"],
  },
  {
    id: "sample-owner",
    email: "owner@dinemate.test",
    display_name: "Sample Café owner",
    role: "owner",
    canteen_ids: [],
    shop_ids: [],
  },
  {
    id: "sample-venue-manager",
    email: "manager@dinemate.test",
    display_name: "Sample Café manager",
    role: "venue_manager",
    canteen_ids: ["v-sample-cafe"],
    shop_ids: [],
  },
  {
    id: "sample-safety",
    email: "safety@dinemate.test",
    display_name: "Safety officer",
    role: "safety_officer",
    canteen_ids: [],
    shop_ids: [],
  },
];

export function sampleUser(email: string): StaffUser | undefined {
  return SAMPLE_USERS.find((u) => u.email === email.trim().toLowerCase());
}
