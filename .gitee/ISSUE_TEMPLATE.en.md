<!--
This template covers two kinds of feedback. **Delete the half you do not need.**
It exists so that I do not have to ask three rounds of questions to understand you.
-->

## A. It does not work (bug)

**Version**

```
$ allin-governance --version
```

**Exact command you ran + full output (including exit code)**

```text

```

> If the output contains `UnicodeEncodeError` / `charmap`, please also paste
> `echo $PYTHONIOENCODING` (PowerShell: `$env:PYTHONIOENCODING`).

**Environment**

| Item | Value |
| --- | --- |
| OS | |
| Python | |
| Node (write "none" if absent) | |
| Inside Docker / WSL / CI? | |

**If it involves `init`: how long did you get stuck between `init` and the first gate run, and where?**

> This matters more to me than "did it work". Currently the only person who has
> run this successfully is me — and I already know all the answers.

---

## B. Suggestion / a gate judges the wrong thing

**What repetitive problem are you trying to remove?**

> Write "I re-check X every week", not "please support X". The first one tells me
> whether it is worth turning into a gate; the second one does not.

**How do you work around it today?**

**What should the rule become?**

> A good rule reads: "scan every tracked file, exit 1 on XXX".
> If it cannot be written that way, it is a wish, not a rule.
