import type { components } from "./generated/schema";
import type * as T from "./types";

type Schemas = components["schemas"];
type Assignable<A, B> = [A] extends [B] ? true : false;
type Expect<V extends true> = V;

export type ApiContract = [
  Expect<Assignable<Schemas["StudentSummary"], T.StudentSummary>>,
  Expect<Assignable<Schemas["CanteenList"], { server_time: string; items: T.CanteenSummary[] }>>,
  Expect<Assignable<Schemas["CanteenDetail"], T.CanteenDetail>>,
  Expect<Assignable<Schemas["ShopList"], T.ShopList>>,
  Expect<Assignable<Schemas["Menu"], T.Menu>>,
  Expect<Assignable<Schemas["MealStatus"], T.MealStatus>>,
  Expect<Assignable<Schemas["ErrorResponse"], T.ErrorResponse>>,
  Expect<Assignable<Schemas["AlertFeed"], T.AlertFeed>>,
  Expect<Assignable<Schemas["ConsoleOverview"], T.ConsoleOverview>>,
  Expect<Assignable<Schemas["StaffAlertList"], { server_time: string; items: T.StaffAlert[] }>>,
  Expect<Assignable<Schemas["StaffAlertResult"], T.StaffAlert & T.Timestamped>>,
  Expect<Assignable<Schemas["Me"], T.StaffUser>>,
  Expect<Assignable<Schemas["Session"], T.StaffSession>>,
  Expect<Assignable<Schemas["ManagedShopList"], T.ManagedShopList>>,
  Expect<Assignable<Schemas["ShopEditor"], T.ShopEditor>>,
  Expect<Assignable<Schemas["AvailabilityResult"], T.AvailabilityResult>>,
  Expect<Assignable<Schemas["MealScheduleSet"], T.MealScheduleSet>>,
  Expect<Assignable<Schemas["ThresholdList"], T.ThresholdList>>,
  Expect<Assignable<Schemas["ThresholdResult"], T.ThresholdResult>>,
  Expect<Assignable<Schemas["DeviceLayout"], T.DeviceLayout>>,
  Expect<Assignable<Schemas["ManagedDeviceList"], T.ManagedDeviceList>>,
  Expect<Assignable<Schemas["ZoneResult"], T.ZoneResult>>,
  Expect<Assignable<Schemas["SafetyActive"], T.SafetyActive>>,
  Expect<Assignable<Schemas["StaffSafetyEventList"], T.StaffSafetyEventList>>,
  Expect<Assignable<Schemas["StaffSafetyEventResult"], T.StaffSafetyEventResult>>,
  Expect<Assignable<Schemas["SafetySourceList"], T.SafetySourceList>>,
  Expect<Assignable<Schemas["ZoneHistory"], T.ZoneHistory>>,
  Expect<Assignable<Schemas["RecommendationResult"], T.RecommendationResult>>,
  Expect<Assignable<Schemas["CanteenSeats"], T.CanteenSeats>>,
  Expect<Assignable<Schemas["SeatOverview"], T.SeatOverview>>,
  Expect<Assignable<Schemas["ZoneSeatMap"], T.ZoneSeatMap>>,
  Expect<Assignable<Schemas["StayTimes"], T.StayTimes>>,
];
