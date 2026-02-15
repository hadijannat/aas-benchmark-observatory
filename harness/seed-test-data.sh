#!/usr/bin/env bash
set -euo pipefail

# Seeds an AAS server with minimal test data required by aas-test-engines.
# The conformance tool expects at least one AAS shell and one submodel to exist.

API_BASE="${1:?Usage: seed-test-data.sh <api_base_url>}"

echo "Seeding test data at $API_BASE ..."

# Create a minimal submodel first (shell references it)
SUBMODEL_ID="urn:example:submodel:test-1"
curl -sf -X POST "$API_BASE/api/v3.0/submodels" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'"$SUBMODEL_ID"'",
    "idShort": "TestSubmodel",
    "modelType": "Submodel",
    "submodelElements": []
  }' > /dev/null

echo "  Created submodel: $SUBMODEL_ID"

# Create a minimal AAS shell referencing the submodel
SHELL_ID="urn:example:aas:test-1"
SUBMODEL_ID_B64=$(printf '%s' "$SUBMODEL_ID" | base64 -w0 2>/dev/null || printf '%s' "$SUBMODEL_ID" | base64)
curl -sf -X POST "$API_BASE/api/v3.0/shells" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'"$SHELL_ID"'",
    "idShort": "TestShell",
    "modelType": "AssetAdministrationShell",
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
            "value": "'"$SUBMODEL_ID"'"
          }
        ]
      }
    ]
  }' > /dev/null

echo "  Created shell: $SHELL_ID"
echo "Seeding complete."
