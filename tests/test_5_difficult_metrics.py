import asyncio

import httpx
from sqlalchemy import select

from src.api.auth import create_access_token
from src.api.routes import get_db_session
from src.models.db import UserModel

TEST_CASES = [
    {
        "id": "case_1_cancellation_rate",
        "name": "Tỷ lệ hủy đơn hàng (Order Cancellation Rate)",
        "prompt": "tôi muốn tính tỷ lệ hủy đơn",
    },
    {
        "id": "case_2_gross_margin",
        "name": "Biên lợi nhuận gộp (Gross Margin)",
        "prompt": "tính biên lợi nhuận gộp",
    },
    {
        "id": "case_3_aov",
        "name": "Giá trị đơn hàng trung bình (Average Order Value)",
        "prompt": "tính giá trị đơn hàng trung bình aov",
    },
    {
        "id": "case_4_cart_abandonment",
        "name": "Tỷ lệ bỏ giỏ hàng (Cart Abandonment Rate)",
        "prompt": "tính tỷ lệ khách bỏ giỏ hàng không mua",
    },
    {
        "id": "case_5_delivery_lead_time",
        "name": "Thời gian giao hàng trung bình (Delivery Lead Time)",
        "prompt": "tính thời gian giao hàng trung bình cho khách",
    },
]


async def run_test():
    token = None
    async for db in get_db_session():
        u = (await db.execute(select(UserModel).where(UserModel.id == 2))).scalar_one()
        token = create_access_token(u)
        break

    headers = {"Authorization": f"Bearer {token}"}
    results = []

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=240.0) as client:
        for idx, case in enumerate(TEST_CASES, 1):
            print(f"\n{'=' * 70}", flush=True)
            print(f"TEST CASE {idx}/5: {case['name']}", flush=True)
            print(f'User Request: "{case["prompt"]}"', flush=True)
            print(f"{'=' * 70}", flush=True)

            # Turn 1: Send request
            print(f"--> Sending Turn 1 request: {case['prompt']}", flush=True)
            resp1 = await client.post(
                "/api/v1/semantic/2/chat",
                json={"message": case["prompt"]},
                headers=headers,
            )
            d1 = resp1.json()
            session_id = d1.get("session_id")
            clar = d1.get("clarification")
            suggestions1 = d1.get("suggestions") or []

            # Verification 1: Must clarify, must NOT create metric immediately
            clar_ok = clar is not None and len(clar.get("options", [])) >= 2
            no_immediate_metric = len(suggestions1) == 0

            print(f"Turn 1 Clarification Triggered: {'PASS' if clar_ok else 'FAIL'}", flush=True)
            print(f"Turn 1 No Immediate Metric:     {'PASS' if no_immediate_metric else 'FAIL'}", flush=True)
            if clar:
                print(f"Clarification Prompt: {clar.get('prompt')}", flush=True)
                for opt in clar.get("options", []):
                    print(f"  - [{opt['id']}]: {opt['label']}", flush=True)

            if not clar_ok:
                results.append(
                    {
                        "case": case["name"],
                        "status": "FAIL_TURN_1",
                        "reason": "Clarification not triggered or < 2 options",
                    }
                )
                continue

            # Turn 2: Pick the last option
            chosen_opt = clar["options"][-1]
            chosen_id = chosen_opt["id"]
            chosen_label = chosen_opt["label"]

            refreshed = await client.get(
                f"/api/v1/semantic/2/chat/sessions/{session_id}",
                headers=headers,
            )
            asst_msg_id = refreshed.json()["messages"][-1]["id"]

            print(f'\n--> Turn 2 User selects: [{chosen_id}] "{chosen_label}"...', flush=True)
            resp2 = await client.post(
                "/api/v1/semantic/2/chat",
                json={
                    "session_id": session_id,
                    "message": chosen_label,
                    "clarification_selection": {
                        "assistant_message_id": asst_msg_id,
                        "option_id": chosen_id,
                    },
                },
                headers=headers,
            )
            d2 = resp2.json()
            suggestions2 = d2.get("suggestions") or []

            # Verification 2: Must generate metric suggestion with formula, base_entity, and dimensions
            metric_ok = False
            details = {}
            if suggestions2:
                sug = suggestions2[0]
                m_def = sug.get("definition", {}).get("metric", {})
                m_name = m_def.get("name")
                m_entity = m_def.get("base_entity")
                m_formula = m_def.get("formula")
                m_dims = m_def.get("dimensions", [])
                m_filters = m_def.get("filters", [])
                metric_ok = bool(m_name and m_entity and m_formula)
                details = {
                    "name": m_name,
                    "base_entity": m_entity,
                    "formula": m_formula,
                    "dimensions": m_dims,
                    "filters": m_filters,
                }
                print(f"Turn 2 Metric Created:          {'PASS' if metric_ok else 'FAIL'}", flush=True)
                print(f"  Metric Name:  {m_name}", flush=True)
                print(f"  Base Entity:  {m_entity}", flush=True)
                print(f"  Formula:      {m_formula}", flush=True)
                print(f"  Dimensions:   {m_dims}", flush=True)
                print(f"  Filters:      {m_filters}", flush=True)
            else:
                print("Turn 2 Metric Created:          FAIL (no suggestions returned)", flush=True)

            results.append(
                {
                    "case": case["name"],
                    "turn1_clarification": clar_ok,
                    "turn1_no_premature_metric": no_immediate_metric,
                    "turn2_metric_created": metric_ok,
                    "details": details,
                }
            )

    print(f"\n{'=' * 70}", flush=True)
    print("FINAL SUMMARY REPORT FOR 5 DIFFICULT METRICS", flush=True)
    print(f"{'=' * 70}", flush=True)
    passed_count = sum(1 for r in results if r.get("turn1_clarification") and r.get("turn2_metric_created"))
    for r in results:
        status = "PASSED" if (r.get("turn1_clarification") and r.get("turn2_metric_created")) else "FAILED"
        print(f"[{status}] {r['case']}", flush=True)
        if r.get("details"):
            d = r["details"]
            print(
                f"         Entity: {d.get('base_entity')}, Formula: {d.get('formula')}, Dims: {d.get('dimensions')}",
                flush=True,
            )
    print(f"\nTotal: {passed_count}/{len(TEST_CASES)} passed.", flush=True)


if __name__ == "__main__":
    asyncio.run(run_test())
