"""Fail if a refresh dropped any year that the committed data already had.

Live feeds sometimes go down; the notebooks degrade gracefully, but that must not be
allowed to silently shrink the published or committed data. Run from the repo root
after the AB/BC/CA notebooks:

    uv run python -m dashboard.check_data [git-ref]   # default ref: HEAD

Revisions to an existing year's totals are fine; only missing years are an error.
"""
import io
import subprocess
import sys

import pandas as pd

from dashboard import charts


def years(df):
    return set(df['Year'].astype(int))


def main(ref='HEAD'):
    root = charts.DATA_DIR.parent
    problems = []
    for region, path in charts.DATA_FILES.items():
        rel = path.relative_to(root).as_posix()
        committed = subprocess.run(['git', 'show', f'{ref}:{rel}'], cwd=root,
                                   capture_output=True, text=True)
        if committed.returncode != 0:
            print(f'{region}: no committed copy at {ref}, skipping')
            continue
        before = years(pd.read_csv(io.StringIO(committed.stdout)))
        after = years(pd.read_csv(path))
        missing = sorted(before - after)
        added = sorted(after - before)
        print(f'{region}: {min(after)}-{max(after)}, {len(after)} years'
              + (f'; new: {added}' if added else '')
              + (f'; MISSING: {missing}' if missing else ''))
        if missing:
            problems.append(f'{rel} lost years {missing} compared with {ref}')

    if problems:
        print('\nRefusing to continue: ' + '; '.join(problems)
              + '. A live feed was probably unavailable; see the notebook output above.',
              file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main(*sys.argv[1:])
