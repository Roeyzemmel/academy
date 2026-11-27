"""machine_notes.py: the machine margin notes, typed (#110) or not, parsed from tex."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fixtures import SCRIPTS  # noqa: E402

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import machine_notes as mn  # noqa: E402

M = ("Claude", "cl")


class ScanTests(unittest.TestCase):
    def test_untyped_note_keeps_todays_form(self):
        (n,) = mn.scan("Text \\Claude{a plain note} more.\n", M)
        self.assertEqual((n["macro"], n["kind"], n["body"], n["line"]),
                         ("Claude", None, "a plain note", 1))
        self.assertEqual(n["raw"], "\\Claude{a plain note}")

    def test_typed_notes(self):
        text = ("\\Claude[prov]{T-0123: from x}\n\\Claude [await] {T-0456 re-verify}\n"
                "\\Claude[human]{which one?}\n\\Claude[ Check ]{unverified}\n")
        got = [(n["kind"], n["body"], n["line"]) for n in mn.scan(text, M)]
        self.assertEqual(got, [("prov", "T-0123: from x", 1), ("await", "T-0456 re-verify", 2),
                               ("human", "which one?", 3), ("check", "unverified", 4)])

    def test_an_unknown_kind_is_kept_as_written(self):
        (n,) = mn.scan("\\Claude[later]{x}", M)
        self.assertEqual(n["kind"], "later")
        self.assertNotIn("later", mn.KINDS)

    def test_macro_names_are_whole_words(self):
        text = "\\clearpage \\claim{x} \\cl{inline} \\Claudette{no} \\Claude{yes}"
        self.assertEqual([(n["macro"], n["body"]) for n in mn.scan(text, M)],
                         [("cl", "inline"), ("Claude", "yes")])

    def test_nested_and_escaped_braces(self):
        (n,) = mn.scan("\\Claude{see \\cref{lem:a} and $\\{x\\}$ {grouped}} tail", M)
        self.assertEqual(n["body"], "see \\cref{lem:a} and $\\{x\\}$ {grouped}")

    def test_comments_are_skipped_and_braces_in_them_do_not_count(self):
        text = ("% \\Claude{commented out}\n50\\% done \\Claude{a % note } with a comment\n"
                "rest}\n")
        (n,) = mn.scan(text, M)
        self.assertEqual(n["body"], "a % note } with a comment\nrest")
        self.assertEqual((n["line"], n["end_line"]), (2, 3))

    def test_a_linebreak_before_the_name_is_no_call(self):
        self.assertEqual(mn.scan("a\\\\Claude{x}", M), [])

    def test_unclosed_note_is_reported(self):
        (n,) = mn.scan("ok \\Claude{never closed\n", M)
        self.assertTrue(n["unclosed"])
        self.assertIsNone(n["body"])

    def test_default_macros_from_config(self):
        self.assertEqual(mn.machine_macros({}), ("Claude", "cl"))
        cfg = {"author": {"noteMacros": {"machine": ["\\Bot"]}}}
        self.assertEqual(mn.machine_macros(cfg), ("Bot",))
        self.assertEqual([n["body"] for n in mn.scan("\\Claude{a}\\Bot{b}", ("Bot",))], ["b"])


class TextTests(unittest.TestCase):
    def test_tickets_in_order_of_first_mention(self):
        self.assertEqual(mn.tickets("T-0456 after T-12345, T-0456 again; XT-1111, T-12"),
                         ["T-0456", "T-12345"])

    def test_plain_strips_markup(self):
        self.assertEqual(mn.plain("see \\cref{lem:a}, $x_1$~and \\texttt{a\\_b} % hidden\nok"),
                         "see lem:a, x_1 and a_b ok")

    def test_estimate_lines(self):
        self.assertEqual(mn.estimate_lines("x" * 30, 30), 1)
        self.assertEqual(mn.estimate_lines("x" * 31, 30), 2)
        self.assertEqual(mn.estimate_lines("", 30), 1)
        self.assertEqual(mn.estimate_lines("\\textbf{%s}" % ("y" * 60), 30), 2)

    def test_note_limits(self):
        self.assertEqual(mn.note_limits({}), (3, mn.DEFAULT_LINE_CHARS))
        cfg = {"author": {"notes": {"maxLines": 2, "lineChars": 50}}}
        self.assertEqual(mn.note_limits(cfg), (2, 50))
        self.assertEqual(mn.note_limits({"author": {"notes": {"maxLines": 0}}})[0], 3)


class SignatureTests(unittest.TestCase):
    def test_signature_survives_moves_and_aliases_but_not_kind_or_text(self):
        a = mn.scan("\\Claude{same  text}", M)[0]
        b = mn.scan("\n\nabove\n\\cl{same\ntext}", M)[0]
        c = mn.scan("\\Claude[prov]{same text}", M)[0]
        d = mn.scan("\\Claude{other text}", M)[0]
        self.assertEqual(mn.signature(a), mn.signature(b))
        self.assertNotEqual(mn.signature(a), mn.signature(c))
        self.assertNotEqual(mn.signature(a), mn.signature(d))

    def test_context_changes_with_a_reply_in_the_paragraph_only(self):
        base = "Intro.\n\nA claim. \\Claude{is this right?}\nMore.\n\nNext para.\n"
        moved = "Intro.\nAn added line above.\n\nA claim. \\Claude{is this right?}\nMore.\n\nNext para.\n"
        reply = "Intro.\n\nA claim. \\Claude{is this right?} \\Ada{yes}\nMore.\n\nNext para.\n"
        far = "Intro.\n\nA claim. \\Claude{is this right?}\nMore.\n\nNext para. \\Ada{x}\n"

        def ctx(t):
            return mn.context_hash(t, mn.scan(t, M)[0])
        self.assertEqual(ctx(base), ctx(moved))
        self.assertNotEqual(ctx(base), ctx(reply))
        self.assertEqual(ctx(base), ctx(far))


if __name__ == "__main__":
    unittest.main()
