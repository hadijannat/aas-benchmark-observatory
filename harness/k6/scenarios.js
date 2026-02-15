import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL;
const SDK_ID = __ENV.SDK_ID;
const OUTPUT_DIR = __ENV.OUTPUT_DIR;

export const options = {
  scenarios: {
    smoke: {
      executor: "per-vu-iterations",
      exec: "default",
      vus: 1,
      iterations: 10,
      startTime: "0s",
    },
    load: {
      executor: "constant-vus",
      exec: "default",
      vus: 10,
      duration: "60s",
      startTime: "0s",
    },
    spike: {
      executor: "ramping-vus",
      exec: "default",
      startVUs: 0,
      startTime: "0s",
      stages: [
        { duration: "30s", target: 50 },
        { duration: "30s", target: 50 },
        { duration: "10s", target: 0 },
      ],
    },
  },
};

export default function () {
  const shellsRes = http.get(`${BASE_URL}/api/v3.0/shells`);
  check(shellsRes, {
    "GET /shells status is 200": (r) => r.status === 200,
  });

  const submodelsRes = http.get(`${BASE_URL}/api/v3.0/submodels`);
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
