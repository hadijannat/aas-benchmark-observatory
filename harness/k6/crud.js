import http from "k6/http";
import { check, group } from "k6";
import encoding from "k6/encoding";

const BASE_URL = __ENV.BASE_URL;
const SDK_ID = __ENV.SDK_ID;
const OUTPUT_DIR = __ENV.OUTPUT_DIR;

export const options = {
  vus: 5,
  iterations: 100,
};

function base64UrlEncode(id) {
  return encoding.b64encode(id, "rawurl");
}

export default function () {
  const shellId = `urn:example:aas:bench:${__VU}:${__ITER}`;
  const params = {
    headers: { "Content-Type": "application/json" },
  };

  group("Create AAS Shell", function () {
    const payload = JSON.stringify({
      id: shellId,
      idShort: `bench-shell-${__VU}-${__ITER}`,
      assetInformation: {
        assetKind: "Instance",
        globalAssetId: `urn:example:asset:${__VU}:${__ITER}`,
      },
    });

    const res = http.post(`${BASE_URL}/shells`, payload, params);
    check(res, {
      "POST /shells status is 201": (r) => r.status === 201,
    });
  });

  group("Read AAS Shell", function () {
    const res = http.get(
      `${BASE_URL}/shells/${base64UrlEncode(shellId)}`
    );
    check(res, {
      "GET /shells/{id} status is 200": (r) => r.status === 200,
    });
  });

  group("Delete AAS Shell", function () {
    const res = http.del(
      `${BASE_URL}/shells/${base64UrlEncode(shellId)}`
    );
    check(res, {
      "DELETE /shells/{id} status is 200 or 204": (r) =>
        r.status === 200 || r.status === 204,
    });
  });
}

export function handleSummary(data) {
  return {
    [`${OUTPUT_DIR}/k6_crud_${SDK_ID}.json`]: JSON.stringify(data),
  };
}
