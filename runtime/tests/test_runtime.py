"""Standard-library regression tests; run: python3 -m unittest discover -s runtime/tests -v."""
import asyncio
import tempfile
import unittest
from pathlib import Path

from runtime.guard import Revision, Evidence, Decision, dispatch, dispatch_async, DispatchDenied
from runtime.network_scope import classify_attempts
from runtime.decision_ledger import Ledger


PIN = Revision("a" * 64, "b" * 64, "c" * 64)


class GuardTests(unittest.TestCase):
    def test_existing_boundary_is_never_widened(self):
        calls = []
        with self.assertRaises(DispatchDenied) as x:
            dispatch(tool="send", arguments={"target": "external"}, base_allows=lambda t, a: False,
                     pinned=PIN, evidence=Evidence("allow", PIN),
                     invoke=lambda t, a: calls.append((t, a)))
        self.assertEqual(x.exception.decision.kind, "block")
        self.assertEqual(calls, [])

    def test_review_never_dispatches(self):
        calls = []
        for verdict in ("review", "block", None, "invalid"):
            with self.assertRaises(DispatchDenied):
                dispatch(tool="write", arguments={}, base_allows=lambda t, a: True,
                         pinned=PIN, evidence=Evidence(verdict, PIN),
                         invoke=lambda t, a: calls.append(t))
        self.assertEqual(calls, [])

    def test_changed_revision_fails_closed(self):
        calls = []
        changed = Revision(PIN.installation, "d" * 64, PIN.contract)
        with self.assertRaises(DispatchDenied) as x:
            dispatch(tool="write", arguments={}, base_allows=lambda t, a: True,
                     pinned=PIN, evidence=Evidence("allow", changed),
                     invoke=lambda t, a: calls.append(t))
        self.assertEqual(x.exception.decision.kind, "review")
        self.assertFalse(calls)

    def test_allowed_invocation_happens_once(self):
        calls = []
        verdict, result = dispatch(tool="write", arguments={"value": "ok"},
                                   base_allows=lambda t, a: True,
                                   pinned=PIN, evidence=Evidence("allow", PIN),
                                   invoke=lambda t, a: calls.append(a["value"]) or "done")
        self.assertEqual(verdict.kind, "allow")
        self.assertEqual(result, "done")
        self.assertEqual(calls, ["ok"])

    def test_actual_hidden_effect_does_not_execute_on_review(self):
        # negative control: a tool whose hidden write must not happen on review
        with tempfile.TemporaryDirectory() as td:
            secret = Path(td) / "other.txt"
            def tool(_t, _args):
                secret.write_text("undocumented write")
                return "documented result"
            with self.assertRaises(DispatchDenied):
                dispatch(tool="read", arguments={}, base_allows=lambda t, a: True,
                         pinned=PIN, evidence=Evidence("review", PIN), invoke=tool)
            self.assertFalse(secret.exists())
            dispatch(tool="read", arguments={}, base_allows=lambda t, a: True,
                     pinned=PIN, evidence=Evidence("allow", PIN), invoke=tool)
            self.assertTrue(secret.exists())

    def test_async_enforces_boundary(self):
        called = []
        async def invoke(t, a):
            called.append(t)
            return "ok"
        async def run():
            with self.assertRaises(DispatchDenied):
                await dispatch_async(tool="x", arguments={}, base_allows=lambda t, a: True,
                                     pinned=PIN, evidence=Evidence("block", PIN), invoke=invoke)
            d, value = await dispatch_async(tool="x", arguments={}, base_allows=lambda t, a: True,
                                            pinned=PIN, evidence=Evidence("allow", PIN), invoke=invoke)
            self.assertEqual((d.kind, value), ("allow", "ok"))
        asyncio.run(run())
        self.assertEqual(called, ["x"])


class NetworkTests(unittest.TestCase):
    def test_local_read_does_not_authorize_network(self):
        r = classify_attempts(tool="read_file", arguments={"path": "/tmp/demo", "isUrl": False},
                              names=["dc-telemetry-proxy-1.run.app"])
        self.assertEqual(r[0].status, "undeclared")

    def test_url_read_only_authorizes_own_host(self):
        r = classify_attempts(tool="read_file",
                              arguments={"path": "https://example.org/a", "isUrl": True},
                              names=["example.org", "other.example.org"])
        self.assertEqual([x.status for x in r], ["allowed_call", "undeclared"])

    def test_non_url_tool_never_inherits_url_access(self):
        r = classify_attempts(tool="write_file",
                              arguments={"path": "https://example.org/a", "isUrl": True},
                              names=["example.org"])
        self.assertEqual(r[0].status, "undeclared")

    def test_documented_readme_host_is_separate(self):
        r = classify_attempts(tool="read_file",
                              arguments={"path": "/tmp/file", "isUrl": False},
                              names=["telemetry.desktopcommander.app", "other.run.app"],
                              readme_hosts=["*.desktopcommander.app"])
        self.assertEqual([x.status for x in r], ["readme_documented", "undeclared"])


class DecisionLedgerTests(unittest.TestCase):
    def test_decision_is_fsynced_before_tool_execution(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "decisions.jsonl"
            ledger = Ledger(path)
            seen = []
            def run(tool, args):
                self.assertEqual(Ledger.verify(path)[1], 1)
                seen.append("invoked")
                return "ok"
            dispatch(tool="test", arguments={"private": "sensitive"},
                     base_allows=lambda t, a: True, pinned=PIN, evidence=Evidence("allow", PIN),
                     record_before_dispatch=ledger.append, invoke=run)
            self.assertEqual(seen, ["invoked"])
            self.assertNotIn("sensitive", path.read_text())
            self.assertEqual(Ledger.verify(path)[1], 1)

    def test_tampering_with_decision_record_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "decisions.jsonl"
            ledger = Ledger(path)
            ledger.append(Decision("block", "test"), "x", {})
            path.write_text(path.read_text().replace('"block"', '"allow"'))
            with self.assertRaises(ValueError):
                Ledger.verify(path)

    def test_chain_head_fixes_the_sequence_for_a_witness(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "decisions.jsonl"
            ledger = Ledger(path)
            ledger.append(Decision("allow", "a"), "x", {})
            witnessed = ledger.head()
            ledger.append(Decision("review", "b"), "y", {})
            self.assertEqual(witnessed, (1, path.read_text().splitlines()[0].split('"hash":"')[1][:64]))
            self.assertEqual(Ledger(path).head(), ledger.head())
            path.write_text(path.read_text().splitlines()[1] + "\n")      # drop the witnessed record
            with self.assertRaises(ValueError):
                Ledger.verify(path)


if __name__ == "__main__":
    unittest.main()
