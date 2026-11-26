"""Run this project's full unittest suite and upgrade journey."""
import sys
import traceback
import unittest


def main():
    suite = unittest.defaultTestLoader.discover('tests', top_level_dir='.')
    if suite.countTestCases():
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    else:
        print('No tests discovered in tests/', file=sys.stderr)
        result = unittest.TestResult()

    upgrade_ok = True
    try:
        import upgrade_walkthrough
        upgrade_walkthrough.main()
    except Exception:
        traceback.print_exc()
        upgrade_ok = False

    for status, failed_cases in (
        ('FAIL', (test for test, _ in result.failures)),
        ('ERROR', (test for test, _ in result.errors)),
        ('UNEXPECTED_SUCCESS', result.unexpectedSuccesses),
    ):
        for test in failed_cases:
            print(f'{status} {test.id()}')
    successful = result.testsRun > 0 and result.wasSuccessful()
    print(f'TEST SUMMARY total={result.testsRun} failures={len(result.failures)} '
          f'errors={len(result.errors)} skipped={len(result.skipped)} '
          f'expected_failures={len(result.expectedFailures)} '
          f'unexpected_successes={len(result.unexpectedSuccesses)} '
          f'result={"PASS" if successful else "FAIL"}')
    print(f'UPGRADE SUMMARY result={"PASS" if upgrade_ok else "FAIL"}')
    return 0 if successful and upgrade_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
