import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { TripRow } from "../repos/trips.js";
import * as tripsRepo from "../repos/trips.js";

const API_NODE_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const REPO_ROOT = path.resolve(API_NODE_ROOT, "..");

function resolvePython(): string {
  const fromEnv = process.env.PYTHON_PATH?.trim();
  if (fromEnv) return fromEnv;
  const venv = path.join(REPO_ROOT, ".venv/bin/python");
  if (fs.existsSync(venv)) return venv;
  return "python3";
}

export async function repairProgramRoutes(input: {
  program: Record<string, unknown>;
  tripId: number;
  city: string;
  dates: string;
  transport?: string;
  pace?: string;
}): Promise<Record<string, unknown>> {
  const script = path.join(REPO_ROOT, "scripts/repair_program_cli.py");
  if (!fs.existsSync(script)) {
    return input.program;
  }
  const payload = JSON.stringify({
    program: input.program,
    trip_id: input.tripId,
    city: input.city,
    dates: input.dates,
    transport: input.transport ?? "mixed",
    pace: input.pace ?? "moderate",
  });
  return new Promise((resolve, reject) => {
    const child = spawn(resolvePython(), [script], {
      cwd: REPO_ROOT,
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf-8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf-8");
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `repair_program_cli exit ${code}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout) as Record<string, unknown>);
      } catch (err) {
        reject(err);
      }
    });
    child.stdin.write(payload);
    child.stdin.end();
  });
}

export async function repairProgramForTrip(
  tripId: number,
  trip: TripRow,
  program: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  try {
    const prefs = await tripsRepo.getPreferences(tripId);
    return await repairProgramRoutes({
      program,
      tripId,
      city: trip.city,
      dates: trip.dates,
      transport: String(prefs?.transport_preference ?? "mixed"),
      pace: String(prefs?.pace ?? "moderate"),
    });
  } catch (err) {
    console.warn(
      "[repairProgram] fallback to stored program:",
      err instanceof Error ? err.message : err,
    );
    return program;
  }
}
