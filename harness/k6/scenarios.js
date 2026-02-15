import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL;
const SDK_ID = __ENV.SDK_ID;
const OUTPUT_DIR = __ENV.OUTPUT_DIR;
const SCENARIO = __ENV.SCENARIO;

const allScenarios = {
  smoke: {
    executor: "per-vu-iterations",
    exec: "default",
    vus: 1,
    iterations: 10,
  },
  load: {
    executor: "constant-vus",
    exec: "default",
    vus: 10,
    duration: "60s",
  },
  spike: {
    executor: "ramping-vus",
    exec: "default",
    startVUs: 0,
    stages: [
      { duration: "30s", target: 50 },
      { duration: "30s", target: 50 },
      { duration: "10s", target: 0 },
    ],
  },
};

// If SCENARIO env var is set, run only that scenario; otherwise run all
export const options = {
  scenarios: SCENARIO
    ? { [SCENARIO]: allScenarios[SCENARIO] }
    : allScenarios,
};

export default function () {
  const shellsRes = http.get(`${BASE_URL}/shells`);
  check(shellsRes, {
    "GET /shells status is 200": (r) => r.status === 200,
  });

  const submodelsRes = http.get(`${BASE_URL}/submodels`);
  check(submodelsRes, {
    "GET /submodels status is 200": (r) => r.status === 200,
  });

  sleep(1);
}

export function handleSummary(data) {
  return {
    [`${OUTPUT_DIR}/k6_summary_${SDK_ID}.json`]: JSON.stringify(data),
  };
}
