import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { AuthProvider } from "../state/AuthContext";
import Login from "./Login";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, api: { post: vi.fn() } };
});

function renderLogin() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes><Route path="/login" element={<Login />} /></Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("Login", () => {
  beforeEach(() => sessionStorage.clear());

  it("shows backend authentication errors to the user", async () => {
    api.post.mockRejectedValueOnce({ response: { data: { detail: "Invalid email or password" } } });
    renderLogin();
    fireEvent.change(screen.getByLabelText("College email"), { target: { value: "student@example.edu" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });

  it("requires a longer password when creating an account", () => {
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "New here? Create an account" }));
    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("minlength", "10");
    expect(password).toHaveAttribute("maxlength", "72");
    expect(screen.getByLabelText("Full name")).toBeRequired();
    expect(screen.getByRole("button", { name: "Create account" })).toBeEnabled();
  });

  it("shows field-specific messages for registration validation errors", async () => {
    api.post.mockRejectedValueOnce({
      response: {
        data: {
          detail: [
            {
              type: "string_too_long",
              loc: ["body", "password"],
              msg: "String should have at most 72 characters",
              input: "redacted",
            },
          ],
        },
      },
    });
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "New here? Create an account" }));
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Test Student" } });
    fireEvent.change(screen.getByLabelText("College email"), { target: { value: "student@example.edu" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a".repeat(73) } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "password: String should have at most 72 characters",
    );
  });
});
