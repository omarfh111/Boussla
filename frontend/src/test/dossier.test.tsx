import { afterEach, expect, it } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { CauseProgressList } from "../dossier/CauseProgress";
import type { CauseProgress } from "../api/types";

afterEach(cleanup);

const cause = (over: Partial<CauseProgress>): CauseProgress => ({
  transaction_id: "TX-1",
  family: "QUANTITY",
  raw_contribution: "40",
  current_contribution: "20",
  stage: "EVIDENCE_RECEIVED",
  provisional: true,
  reason_code: "PROJECT_ALLOCATION_EXCEEDS_REFERENCE",
  source_ids: ["DOC-1"],
  ...over,
});

it("shows the server stage and distinguishes provisional progress from confirmed resolution", () => {
  render(
    <CauseProgressList
      causes={[
        cause({}),
        cause({
          transaction_id: "TX-2",
          stage: "RESOLVED",
          current_contribution: "0",
          provisional: false,
        }),
      ]}
    />,
  );
  const rows = document.querySelectorAll(".cause-progress");
  expect(rows).toHaveLength(2);
  expect(
    within(rows[0] as HTMLElement)
      .getByText("Pièce")
      .closest("li"),
  ).toHaveAttribute("aria-current", "step");
  expect(
    within(rows[0] as HTMLElement).getByText(/Réduction provisoire/),
  ).toBeVisible();
  expect(
    within(rows[1] as HTMLElement)
      .getByText("Résolue")
      .closest("li"),
  ).toHaveAttribute("aria-current", "step");
  expect(
    within(rows[1] as HTMLElement).getByText("Résolution confirmée"),
  ).toBeVisible();
  fireEvent.click(
    within(rows[0] as HTMLElement).getByText("Provenance et règle"),
  );
  expect(within(rows[0] as HTMLElement).getByText(/DOC-1/)).toBeVisible();
});
