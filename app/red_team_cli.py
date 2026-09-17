from app.red_team import evaluate_red_team_cases


def main() -> int:
    report = evaluate_red_team_cases()

    print(f"total={report.total}")
    print(f"passed={report.passed}")
    print(f"pass_rate={report.pass_rate:.2%}")

    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"[{status}] {result.case_id} "
            f"blocked={result.blocked} "
            f"approval={result.requires_approval} "
            f"reason={result.reason}"
        )

    return 0 if not report.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())