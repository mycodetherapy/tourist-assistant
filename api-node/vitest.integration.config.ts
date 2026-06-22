import vitestConfig from "./vitest.config.js";

export default {
  ...vitestConfig,
  test: {
    ...vitestConfig.test,
    include: ["test/integration/**/*.test.ts"],
    exclude: [],
    setupFiles: ["test/setup-env.ts"],
  },
};
