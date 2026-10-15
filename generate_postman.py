
import json
from pathlib import Path

project_dir = Path(__file__).parent
spec_path = project_dir / "openapi.json"
output_dir = project_dir / "postman"
output_dir.mkdir(exist_ok=True)

with spec_path.open("r", encoding="utf-8") as file:
    spec = json.load(file)

items = []

for path, methods in spec.get("paths", {}).items():
    for method, details in methods.items():
        if method.lower() not in {
            "get", "post", "put", "patch", "delete"
        }:
            continue

        path_parts = path.strip("/").split("/") if path.strip("/") else []
        postman_path = [
            part[1:-1] if part.startswith("{") and part.endswith("}")
            else part
            for part in path_parts
        ]

        url = {
            "raw": "{{base_url}}" + path,
            "host": ["{{base_url}}"],
            "path": postman_path,
        }

        query_params = [
            {
                "key": param["name"],
                "value": "",
                "disabled": True,
            }
            for param in details.get("parameters", [])
            if param.get("in") == "query"
        ]

        if query_params:
            url["query"] = query_params

        request = {
            "method": method.upper(),
            "header": [],
            "url": url,
            "description": details.get("summary", ""),
        }

        if method.lower() in {"post", "put", "patch"}:
            if "requestBody" in details:
                request["header"].append({
                    "key": "Content-Type",
                    "value": "application/json",
                })
                request["body"] = {
                    "mode": "raw",
                    "raw": "{}",
                    "options": {"raw": {"language": "json"}},
                }

        if path.startswith("/auth/"):
            request["auth"] = {"type": "noauth"}
        elif path != "/":
            request["auth"] = {
                "type": "bearer",
                "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}],
            }

        items.append({
            "name": details.get("summary", f"{method.upper()} {path}"),
            "request": request,
        })

collection = {
    "info": {
        "name": "Job Application Tracker API",
        "description": "Generated from the project's FastAPI OpenAPI specification.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [
        {"key": "base_url", "value": "http://127.0.0.1:8000"},
        {"key": "token", "value": ""},
    ],
    "item": items,
}

output_path = output_dir / "Job-Application-Tracker.postman_collection.json"
with output_path.open("w", encoding="utf-8") as file:
    json.dump(collection, file, indent=2)

print(f"Created collection with {len(items)} requests:")
print(output_path)
