import axios from "axios";

export const api = axios.create({ baseURL: "/api/v1" });

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem("campus-pilot-token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function messageFromError(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((issue) => {
      if (typeof issue === "string") return issue;
      if (!issue || typeof issue !== "object") return null;

      const location = Array.isArray(issue.loc)
        ? issue.loc.filter((part) => !["body", "query", "path", "header"].includes(part)).join(".")
        : "";
      const message = typeof issue.msg === "string" ? issue.msg : "";
      if (!message) return null;
      const field = location.replaceAll("_", " ");
      return field ? `${field}: ${message}` : message;
    }).filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return "The request could not be completed. Please try again.";
}
