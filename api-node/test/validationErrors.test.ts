import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { buildApp } from "../src/index.js";
import type { FastifyInstance } from "fastify";

describe("request validation errors", () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    app = await buildApp({ enableSwaggerUi: false });
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  it("login short password returns 400", async () => {
    const resp = await app.inject({
      method: "POST",
      url: "/api/auth/login",
      payload: { email: "test@example.com", password: "short" },
    });
    expect(resp.statusCode).toBe(400);
    expect(resp.json()).toEqual({ detail: "Некорректные данные" });
  });

  it("login invalid email returns 400", async () => {
    const resp = await app.inject({
      method: "POST",
      url: "/api/auth/login",
      payload: { email: "not-an-email", password: "validpass1" },
    });
    expect(resp.statusCode).toBe(400);
    expect(resp.json()).toEqual({ detail: "Некорректные данные" });
  });
});
