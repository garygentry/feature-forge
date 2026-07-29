import { expect, test } from "vitest";
import { greet } from "../src/index.js";

test("greet returns a greeting", () => {
  expect(greet("world")).toBe("Hello from world");
});
