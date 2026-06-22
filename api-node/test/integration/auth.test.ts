import { randomBytes } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import "../../src/loadEnv.js";
import { buildApp } from "../../src/index.js";
import { closePool, query } from "../../src/db/pool.js";
import { closeRedis } from "../../src/db/redis.js";
import type { FastifyInstance } from "fastify";

const hasDatabase = Boolean((process.env.DATABASE_URL ?? "").trim());
const testEmail = `integration-${randomBytes(4).toString("hex")}@example.com`;
const testPassword = "secretpass";

describe.skipIf(!hasDatabase)("auth integration", () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    app = await buildApp();
    await app.ready();
  });

  afterAll(async () => {
    await query("DELETE FROM users WHERE email = $1", [testEmail]);
    await app.close();
    await closeRedis();
    await closePool();
  });

  it("register login me", async () => {
    const reg = await app.inject({
      method: "POST",
      url: "/api/auth/register",
      payload: { email: testEmail, password: testPassword },
    });
    expect(reg.statusCode).toBe(201);
    const regBody = reg.json() as { access_token: string };
    expect(regBody.access_token).toBeTruthy();

    const bad = await app.inject({
      method: "POST",
      url: "/api/auth/login",
      payload: { email: testEmail, password: "wrongpass" },
    });
    expect(bad.statusCode).toBe(401);

    const login = await app.inject({
      method: "POST",
      url: "/api/auth/login",
      payload: { email: testEmail, password: testPassword },
    });
    expect(login.statusCode).toBe(200);
    const token = (login.json() as { access_token: string }).access_token;

    const me = await app.inject({
      method: "GET",
      url: "/api/auth/me",
      headers: { authorization: `Bearer ${token}` },
    });
    expect(me.statusCode).toBe(200);
    expect((me.json() as { email: string }).email).toBe(testEmail);
  });

  it("trips require auth", async () => {
    const resp = await app.inject({ method: "GET", url: "/api/trips" });
    expect(resp.statusCode).toBe(401);
  });

  it("health", async () => {
    const resp = await app.inject({ method: "GET", url: "/api/health" });
    expect(resp.statusCode).toBe(200);
    expect(resp.json()).toEqual({ status: "ok" });
  });
});
