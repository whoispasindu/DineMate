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
];
