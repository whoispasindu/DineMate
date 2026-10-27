import { APP_NAME, CanteenArt, Icon, type IconName } from "@dinemate/ui";
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
    <main id="main" className="flex min-h-dvh bg-mint-soft">
      <div className="mx-auto flex w-full max-w-[420px] flex-col px-7 pb-9 pt-14">
        <div className="flex flex-1 flex-col items-center justify-center gap-[22px] text-center">
          <div className="relative h-[168px] w-60">
            <CanteenArt wall="#DCEFE2" className="rounded-[28px]" />
            <span className="absolute -bottom-[18px] -right-3.5 flex h-[72px] w-[72px] items-center justify-center rounded-[22px] border-[5px] border-mint-soft bg-brand text-white">
              <Icon name="leaf" size={36} />
            </span>
          </div>
          <div className="mt-[18px] flex flex-col gap-2.5">
            <h1 className="m-0 text-[34px] font-extrabold tracking-[-0.03em] text-brand-dark">{APP_NAME}</h1>
            <p className="m-0 text-[17px] leading-[1.45] text-ink-2">
              Know where to sit
              <br />
              before you queue.
            </p>
          </div>
          <ul className="m-0 flex list-none flex-wrap justify-center gap-2 p-0">
            {FEATURES.map((f) => (
              <li
                key={f.label}
                className="inline-flex items-center gap-1.5 rounded-full bg-card px-3 py-[7px] text-[13px] font-bold text-ink-2"
              >
                <Icon name={f.icon} size={15} className="text-brand" />
                {f.label}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={start}
            className="flex min-h-[54px] items-center justify-center rounded-2xl border-0 bg-brand text-base font-extrabold text-white hover:bg-brand-dark"
          >
            Get started
          </button>
          {canPrompt || showIosHint ? (
            <button
              type="button"
              onClick={install}
              className="flex min-h-[54px] items-center justify-center gap-2 rounded-2xl border-[1.5px] border-mint-line bg-card text-base font-bold text-brand-dark"
            >
              <Icon name="download" size={18} />
              Install app
            </button>
          ) : null}
          {hintOpen ? (
            <div role="status" className="flex flex-col gap-1.5 rounded-2xl bg-card p-3.5 text-sm text-ink-2">
              <span className="font-extrabold text-ink">Add {APP_NAME} to your Home Screen</span>
              <span className="inline-flex items-center gap-1.5">
                1. Tap <Icon name="share" size={16} className="text-brand" /> Share in Safari
              </span>
              <span>2. Choose “Add to Home Screen”</span>
            </div>
          ) : null}
          <p className="m-0 mt-1.5 text-center text-xs leading-normal text-muted">
            Seat counts are estimates from privacy-preserving sensors.
            <br />
            No video is stored. No face recognition.
          </p>
        </div>
      </div>
    </main>
  );
}
