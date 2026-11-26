import json
from pathlib import Path
from tempfile import TemporaryDirectory

from demo import edit, equal, expect
from tests.support import running_service, two_slots


def slot(key, label, default, predecessor, *, width=2):
    return dict(key=key, label=label, default=default, width=width, max_lines=2,
                **{"from": predecessor})


def values(state):
    return [[row["key"], row["text"], row["overridden"]] for row in state["slots"]]


def main():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "upgrade.sqlite3"
        with running_service(path) as client:
            draft = expect(client, 201, "/templates/drafts", {
                "title": "首站", "slots": two_slots(),
            })["draft"]
            base = expect(client, 201, "/templates/drafts/" + draft + "/publish", {})["template"]
            asset = expect(client, 201, "/assets", {
                "name": "桥景", "kind": "image", "alt": "木桥",
            })["revision"]
            content = {"template": base, "assets": [asset]}
            editorial = expect(client, 201, "/signs", content)
            control = expect(client, 201, "/signs", content)
            sign = editorial["sign"]
            sign_path = "/signs/" + sign
            control_path = "/signs/" + control["sign"]
            original = edit(client, sign, "A", "write", text="河岸")
            old_proof = expect(client, 201, sign_path + "/proofs", {"revision": original["revision"]})
            old_release = expect(client, 201, sign_path + "/releases", {"proof": old_proof["proof"]})
            receipt_path = "/releases/" + old_release["release"]
            fixed = client.request(receipt_path)
            equal(fixed.status, 200)

            publish_path = "/templates/" + base + "/revisions"
            moved = slot("L", "左栏", "河畔", "A", width=1)
            new_right = slot("R", "右栏", "码头", None)
            bridge = slot("B2", "桥栏", "石桥", "B")
            second = expect(client, 201, publish_path, {
                "title": "次站", "slots": [moved, new_right, bridge],
            })["template"]
            expect(client, 400, publish_path, {
                "title": "重复承接", "slots": [moved, dict(new_right, **{"from": "A"})],
            })
            second_request = {"target": second}
            upgraded = expect(client, 200, sign_path + "/upgrade", second_request)
            equal(values(upgraded), [["L", "河岸", True], ["R", "码头", False], ["B2", "石桥", False]])
            equal(upgraded["assets"], [asset])
            equal(upgraded["template"], second)
            if upgraded["revision"] == original["revision"]:
                raise AssertionError("换版没有生成新修订")
            equal(expect(client, 200, sign_path + "/upgrade", second_request), upgraded)
            current_proof = expect(client, 201, sign_path + "/proofs", {"revision": upgraded["revision"]})
            equal([row["lines"] for row in current_proof["slots"]], [["河", "岸"], ["码头"], ["石桥"]])
            current_release = expect(client, 201, sign_path + "/releases", {"proof": current_proof["proof"]})
            equal(current_release["source"]["template"], second)
            expect(client, 409, sign_path + "/releases", {"proof": old_proof["proof"]})

            third = expect(client, 201, "/templates/" + second + "/revisions", {
                "title": "末站", "slots": [slot("M", "展文", "沿岸", "L"),
                                          slot("A", "附栏", "潮线", None)],
            })["template"]
            third_request = {"target": third}
            expect(client, 409, control_path + "/upgrade", third_request)
            compare = expect(client, 200, control_path + "/upgrade", second_request)
            equal(values(compare), [["L", "河畔", False], ["R", "码头", False], ["B2", "石桥", False]])
            edit(client, sign, "B2", "write", text="石桥")
            blocked = edit(client, sign, "R", "write", text="")
            rejection = expect(client, 409, sign_path + "/upgrade", third_request)
            equal(rejection["retired_slots"], ["R", "B2"])
            equal(expect(client, 200, sign_path), blocked)
            equal(expect(client, 200, sign_path + "/upgrade", second_request), blocked)
            edit(client, sign, "R", "reset")
            edit(client, sign, "B2", "reset")
            latest = expect(client, 200, sign_path + "/upgrade", third_request)
            equal(values(latest), [["M", "河岸", True], ["A", "潮线", False]])

        with running_service(path) as reopened:
            historical = expect(reopened, 201, sign_path + "/proofs", {"revision": original["revision"]})
            equal(dict(historical, proof=old_proof["proof"]), old_proof)
            equal(expect(reopened, 200, "/proofs/" + old_proof["proof"]), old_proof)
            reclaimed_reply = reopened.request(receipt_path)
            equal(reclaimed_reply.status, 200)
            reclaimed = reclaimed_reply.body
            equal(reclaimed_reply.raw, fixed.raw)
            equal(expect(reopened, 200, sign_path), latest)

        first_proof_view = [
            [slot["key"], slot["label"], slot["lines"], slot["overflow"]]
            for slot in old_proof["slots"]
        ]
        print(json.dumps({
            "换版后人工签": values(upgraded), "换版后默认签": values(compare),
            "退役拒绝": rejection["retired_slots"], "重开在用": values(latest),
            "末站完整状态": latest,
            "次站校样": [
                [slot["key"], slot["label"], slot["lines"], slot["overflow"]]
                for slot in current_proof["slots"]
            ],
            "次站定稿来源": current_release["source"],
            "重开旧校样模板": historical["template"],
            "首站校样": {
                "proof": old_proof["proof"],
                "revision": old_proof["revision"],
                "template": old_proof["template"],
                "slots": first_proof_view,
                "overflow": old_proof["overflow"],
                "重出校样除编号外一致": dict(historical, proof=old_proof["proof"]) == old_proof,
            },
            "重开复领发阅号": old_release["release"],
            "首站定稿复领": {
                "release": reclaimed["release"],
                "source": reclaimed["source"],
                "html": reclaimed["html"],
                "bytes_match": reclaimed_reply.raw == fixed.raw,
            },
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
