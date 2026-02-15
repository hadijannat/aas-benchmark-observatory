#!/usr/bin/env bash
set -euo pipefail

# Seeds an AAS server with minimal test data required by aas-test-engines.
# The conformance tool expects at least one AAS shell and one submodel to exist.

API_BASE="${1:?Usage: seed-test-data.sh <api_base_url>}"

echo "Seeding test data at $API_BASE ..."

post_json() {
  local url="$1"
  local data="$2"
  local description="$3"

  HTTP_CODE=$(curl -s -o /tmp/seed-response.txt -w '%{http_code}' \
    -X POST "$url" \
    -H "Content-Type: application/json" \
    -d "$data")

  if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
    echo "  Created $description (HTTP $HTTP_CODE)"
  else
    echo "  FAILED to create $description (HTTP $HTTP_CODE):" >&2
    cat /tmp/seed-response.txt >&2
    echo >&2
    return 1
  fi
}

# Create a submodel with at least one element (required by aas-test-engines
# which needs an idShortPath for element-level endpoint tests)
post_json "$API_BASE/submodels" '{
  "id": "urn:example:submodel:test-1",
  "idShort": "TestSubmodel",
  "submodelElements": [
    {
      "idShort": "TestProperty",
      "modelType": "Property",
      "valueType": "xs:string",
      "value": "hello"
    }
  ]
}' "submodel urn:example:submodel:test-1"

# Create a minimal AAS shell
post_json "$API_BASE/shells" '{
  "id": "urn:example:aas:test-1",
  "idShort": "TestShell",
  "assetInformation": {
    "assetKind": "Instance",
    "globalAssetId": "urn:example:asset:test-1"
  },
  "submodels": [
    {
      "type": "ModelReference",
      "keys": [
        {
          "type": "Submodel",
          "value": "urn:example:submodel:test-1"
        }
      ]
    }
  ]
}' "shell urn:example:aas:test-1"

echo "Seeding complete."
