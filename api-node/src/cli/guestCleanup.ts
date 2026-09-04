import "../loadEnv.js";
import { closePool } from "../db/pool.js";
import { closeRedis } from "../db/redis.js";
import { runGuestCleanup } from "../services/guestCleanup.js";

async function main(): Promise<void> {
  const stats = await runGuestCleanup();
  console.log(
    JSON.stringify({
      ok: true,
      deleted_users: stats.deletedUsers,
      deleted_user_ids: stats.deletedUserIds,
      deleted_auth_sessions: stats.deletedAuthSessions,
    }),
  );
  await closeRedis();
  await closePool();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
