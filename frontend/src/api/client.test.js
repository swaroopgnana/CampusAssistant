import { describe, expect, it } from "vitest";
import { messageFromError } from "./client";

describe("messageFromError", () => {
  it("returns string API errors", () => {
    expect(messageFromError({ response: { data: { detail: "Invalid email or password" } } }))
      .toBe("Invalid email or password");
  });

  it("formats FastAPI validation errors without rendering their objects", () => {
    expect(messageFromError({
      response: {
        data: {
          detail: [
            { type: "value_error", loc: ["body", "email"], msg: "Enter a valid email address", input: "bad" },
            { type: "string_too_short", loc: ["body", "password"], msg: "String should have at least 10 characters", input: "short" },
          ],
        },
      },
    })).toBe("email: Enter a valid email address; password: String should have at least 10 characters");
  });

  it("uses a fallback for unrecognized error shapes", () => {
    expect(messageFromError({ response: { data: { detail: { unexpected: true } } } }))
      .toBe("The request could not be completed. Please try again.");
  });
});
