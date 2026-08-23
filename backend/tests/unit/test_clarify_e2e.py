"""End-to-end test for the clarification reply flow."""
import httpx
import json
import time

client = httpx.Client(timeout=180.0)

# Login as staff
resp = client.post("http://localhost:8000/api/auth/login", json={
    "email": "admin@carepilot.com",
    "password": "abcdef123456!"
})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("Logged in as admin@carepilot.com")

# 1. Check existing run #9 (awaiting_clarification, dental request)
resp = client.get("http://localhost:8000/api/workflows/9", headers=headers)
run9 = resp.json()
print(f"\n=== Request #9 (existing) ===")
print(f"Status: {run9['status']}")
print(f"Summary: {run9.get('summary')}")
final = run9.get("state", {}).get("final_response", "")
print(f"Clarification Q: {final[:120]}")

# 2. Resume run #9 with a specific answer
time.sleep(3)
resp = client.post("http://localhost:8000/api/workflows/9/resume",
    json={"message": "General dentistry, routine check-up and cleaning please"},
    headers=headers)
print(f"\nResume #9: {resp.status_code}")
if resp.status_code == 200:
    run9b = resp.json()
    print(f"Status: {run9b['status']}")
    print(f"Summary: {run9b.get('summary')}")
    state = run9b.get("state", {})
    print(f"Dept: {state.get('department_name', 'N/A')}")
    print(f"Final: {state.get('final_response', 'N/A')[:200]}")
else:
    print(f"Error: {resp.text[:300]}")

# 3. Create a new workflow that triggers clarification
time.sleep(5)
resp = client.post("http://localhost:8000/api/workflows/run",
    json={"patient_id": 15, "request_text": "I want to see someone about my skin"},
    headers=headers)
print(f"\n=== New Workflow ===")
if resp.status_code == 201:
    new_run = resp.json()
    new_id = new_run["id"]
    print(f"Run #{new_id}: {new_run['status']}")
    print(f"Summary: {new_run.get('summary')}")
    
    if new_run["status"] == "awaiting_clarification":
        # Resume with specific department
        time.sleep(3)
        resp = client.post(f"http://localhost:8000/api/workflows/{new_id}/resume",
            json={"message": "Dermatology, please"},
            headers=headers)
        print(f"\nResume #{new_id}: {resp.status_code}")
        if resp.status_code == 200:
            final_run = resp.json()
            print(f"Status: {final_run['status']}")
            print(f"Summary: {final_run.get('summary')}")
            state = final_run.get("state", {})
            print(f"Dept: {state.get('department_name', 'N/A')}")
            print(f"Appt: {state.get('appointment_id', 'N/A')}")
            print(f"Final: {state.get('final_response', 'N/A')[:200]}")
        else:
            print(f"Error: {resp.text[:300]}")
    elif new_run["status"] == "escalated":
        print("Request was escalated (safety agent)")
    else:
        state = new_run.get("state", {})
        print(f"Dept: {state.get('department_name', 'N/A')}")
        print(f"Final: {state.get('final_response', 'N/A')[:200]}")
elif resp.status_code == 429:
    print("Rate limited - try again later")
else:
    print(f"Error: {resp.text[:300]}")
