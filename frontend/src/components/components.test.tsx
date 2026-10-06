import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExplainabilityViewer from "./ExplainabilityViewer";
import ModelBadge from "./ModelBadge";
import PriorityCard from "./PriorityCard";
import StatusBadge from "./StatusBadge";

// framer-motion's whileInView needs IntersectionObserver, which jsdom lacks.
vi.stubGlobal(
  "IntersectionObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
);

afterEach(cleanup);

describe("PriorityCard", () => {
  it("shows review reasons as text, not colour alone", () => {
    render(
      <PriorityCard
        priority={{
          level: "Medium",
          score: 3.6,
          basis: "Driven by Section 376: severity 10 x confidence 0.36 = 3.6",
          review_required: true,
          review_reasons: ["Section 376 carries a severity of 10 but was predicted with only 36% confidence."],
        }}
      />
    );
    expect(screen.getByRole("note", { name: "Officer review needed" })).toBeTruthy();
    expect(screen.getByText(/predicted with only 36% confidence/)).toBeTruthy();
    expect(screen.getByText(/not a legal finding/)).toBeTruthy();
  });

  it("shows no review box for a confident prediction", () => {
    render(<PriorityCard priority={{ level: "High", score: 9.3, review_required: false, review_reasons: [] }} />);
    expect(screen.queryByRole("note")).toBeNull();
  });
});

describe("StatusBadge", () => {
  it.each(["High", "Medium", "Low"] as const)("names the %s level in text", (level) => {
    render(<StatusBadge level={level} />);
    expect(screen.getByText(level)).toBeTruthy();
  });
});

describe("ModelBadge", () => {
  it("flags a degraded classifier", () => {
    render(<ModelBadge backend="keyword-stub (DistilBERT unavailable)" />);
    expect(screen.getByText(/model unavailable/)).toBeTruthy();
  });

  it("renders nothing without a backend", () => {
    const { container } = render(<ModelBadge backend={null} />);
    expect(container.textContent).toBe("");
  });
});

describe("ExplainabilityViewer", () => {
  it("highlights the attributed tokens of this complaint and labels them for screen readers", () => {
    render(
      <ExplainabilityViewer
        complaintText="The accused snatched my chain and threatened me."
        explanation={[
          { token: "snatched", weight: 0.87 },
          { token: "threatened", weight: 0.8 },
          { token: "not-in-text", weight: 0.9 },
        ]}
      />
    );
    const marks = document.querySelectorAll("mark");
    expect(Array.from(marks).map((m) => m.textContent)).toEqual(["snatched", "threatened"]);
    expect(screen.getByLabelText("snatched, influence weight 0.87")).toBeTruthy();
    expect(document.querySelector("mark[role='button']")).toBeNull();
  });

  it("renders plain text when there is no explanation", () => {
    render(<ExplainabilityViewer complaintText="Nothing to highlight here." explanation={[]} />);
    expect(document.querySelectorAll("mark").length).toBe(0);
    expect(screen.getByText("Nothing to highlight here.")).toBeTruthy();
  });
});
