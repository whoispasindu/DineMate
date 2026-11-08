import { APP_NAME, BrandMark, Icon, TableScene, welcomePhoto, type IconName } from "@dinemate/ui";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router";
import { isStandalone, useInstall } from "../lib/device";
import { welcomeSeen } from "../lib/prefs";

const FEATURES: { icon: IconName; label: string }[] = [
  { icon: "seat", label: "Live seats" },
  { icon: "utensils", label: "Menus" },
  { icon: "clock", label: "Meal times" },
];

export function WelcomeScreen() {
  const navigate = useNavigate();
  const seen = welcomeSeen.use();
  const { canPrompt, showIosHint, promptInstall } = useInstall();
  const [hintOpen, setHintOpen] = useState(false);

  if (seen || isStandalone()) return <Navigate to="/" replace />;

  const start = () => {
    welcomeSeen.set(true);
    navigate("/", { replace: true });
  };

  const install = async () => {
    if (canPrompt) {
      const accepted = await promptInstall();
      if (accepted) start();
      return;
    }
    setHintOpen(true);
  };

  return (
    <main id="main" className="flex min-h-dvh bg-brand text-sand">
      <div className="mx-auto flex w-full max-w-[440px] flex-col px-6 pb-8 pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <BrandMark tone="sand" size={34} />
            <span className="font-display text-xl font-extrabold tracking-[-0.02em]">{APP_NAME}</span>
          </div>
          <span className="text-xs font-medium text-on-dark-faint">Campus canteens</span>
        </div>
        <div className="relative mt-6">
          <div className="h-[300px] overflow-hidden rounded-[200px_200px_28px_28px]">
            <img src={welcomePhoto} alt="" decoding="async" className="block h-full w-full object-cover" />
          </div>
          <div className="edge-sand absolute -bottom-7 left-5 flex items-center gap-2.5 rounded-[18px] bg-sand py-2 pl-2.5 pr-4 text-brand">
            <TableScene width={56} />
            <span className="flex flex-col gap-0.5">
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-purple-ink">
                <span className="h-1.5 w-1.5 rounded-full bg-purple" />
                Live estimates
              </span>
              <span className="font-display text-lg font-extrabold leading-tight">Every canteen</span>
            </span>
          </div>
        </div>
        <div className="mt-12 flex flex-1 flex-col gap-3.5">
          <h1 className="m-0 font-display text-[44px] font-extrabold leading-none tracking-[-0.05em]">
            Know where
            <br />
            to sit <span className="text-held">before</span>
            <br />
            you queue.
          </h1>
          <p className="m-0 max-w-[310px] text-[15.5px] leading-[1.45] text-on-dark-faint">
            Live seat estimates for every canteen, today's menus and meal times. No sign-up.
          </p>
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {FEATURES.map((f) => (
              <li key={f.label} className="inline-flex h-8 items-center gap-1.5 rounded-full bg-white/10 px-3 text-[13px] font-semibold">
                <Icon name={f.icon} size={15} />
                {f.label}
              </li>
            ))}
          </ul>
        </div>
        <div className="mt-8 flex flex-col gap-3">
          <button
            type="button"
            onClick={start}
            className="edge-sand flex min-h-[52px] items-center justify-center gap-2 rounded-[14px] border-0 bg-sand text-base font-bold text-brand"
          >
            Find a seat
            <Icon name="arrowRight" size={18} strokeWidth={2.2} />
          </button>
          {canPrompt || showIosHint ? (
            <button
              type="button"
              onClick={install}
              className="flex min-h-[52px] items-center justify-center gap-2 rounded-[14px] border-[1.5px] border-sand/40 bg-transparent text-base font-bold text-sand"
            >
              <Icon name="download" size={18} />
              Install app
            </button>
          ) : null}
          {hintOpen ? (
            <div role="status" className="flex flex-col gap-1.5 rounded-2xl bg-sand p-3.5 text-sm text-brand">
              <span className="font-bold">Add {APP_NAME} to your Home Screen</span>
              <span className="inline-flex items-center gap-1.5">
                1. Tap <Icon name="share" size={16} /> Share in Safari
              </span>
              <span>2. Choose “Add to Home Screen”</span>
            </div>
          ) : null}
          <p className="m-0 mt-1 text-center text-xs leading-normal text-on-dark-faint">
            Estimates from counts only. No video is stored. No face recognition.
          </p>
        </div>
      </div>
    </main>
  );
}
