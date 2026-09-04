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
    const regBody = reg.json() as { access_token: string; user: { id: number } };
    expect(regBody.access_token).toBeTruthy();
    const sessionCookie = (reg.cookies as { name: string; value: string }[]).find(
      (c) => c.name === "auth_session",
    );
    expect(sessionCookie?.value).toBeTruthy();

    const auditReg = await query<{ action: string }>(
      `SELECT action FROM audit_events
       WHERE user_id = $1 AND action IN ('user.register', 'user.login')
       ORDER BY action`,
      [regBody.user.id],
    );
    expect(auditReg.rows.map((r) => r.action).sort()).toEqual([
      "user.login",
      "user.register",
    ]);

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

    const meCookie = await app.inject({
      method: "GET",
      url: "/api/auth/me",
      cookies: { auth_session: sessionCookie!.value },
    });
    expect(meCookie.statusCode).toBe(200);
    expect((meCookie.json() as { email: string }).email).toBe(testEmail);

    const loggedOut = await app.inject({
      method: "POST",
      url: "/api/auth/logout",
      cookies: { auth_session: sessionCookie!.value },
    });
    expect(loggedOut.statusCode).toBe(204);

    const meAfterLogout = await app.inject({
      method: "GET",
      url: "/api/auth/me",
      cookies: { auth_session: sessionCookie!.value },
    });
    expect(meAfterLogout.statusCode).toBe(401);

    const seen = await query<{ last_seen_at: Date | null }>(
      "SELECT last_seen_at FROM users WHERE id = $1",
      [regBody.user.id],
    );
    expect(seen.rows[0]?.last_seen_at).toBeTruthy();
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

  it("empty byok key is rejected without existing key", async () => {
    const login = await app.inject({
      method: "POST",
      url: "/api/auth/login",
      payload: { email: testEmail, password: testPassword },
    });
    const token = (login.json() as { access_token: string }).access_token;

    const saveEmpty = await app.inject({
      method: "PUT",
      url: "/api/profile/settings",
      headers: { authorization: `Bearer ${token}` },
      payload: { llm_mode: "byok", llm_api_key: "" },
    });
    expect(saveEmpty.statusCode).toBe(428);
  });
});
