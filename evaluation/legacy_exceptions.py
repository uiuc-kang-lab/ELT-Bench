"""Stage-2 verdicts for runs made before a data-model definition changed.

Only the paper re-scoring scripts use this module. eva.py does not, so runs made after a change are judged against the
current definitions without exceptions.

2026-10-22  codebase_community__posts and codebase_community__users, CREATION_DATE: the definitions gained
            `format: YYYY-MM-DD HH:MM:SS`. Earlier runs saw no format, so a CREATION_DATE that differs from the GT only by
            zero fractional seconds ('.0', the source text) or a '+00:00' offset (a Databricks TIMESTAMP export) counts
            as matched.
2026-10-22  airline__airlines: the original definition misspelled FLIGHT_NUMBER_HAD_THE_LONGEST_DELAY_IN_DEPARTURE as
            FLIGHT_NUMBER_HAD_THE_LONEST_DELAY_IN_DEPARTURE. A run that used the misspelled name is compared on that
            column's content.
"""
import re

import pandas as pd

from eva_stage2 import check_corretness

FORMAT_ADDED = {
    ("codebase_community", "codebase_community__posts"): ["creation_date"],
    ("codebase_community", "codebase_community__users"): ["creation_date"],
}
COLUMN_RENAMED = {
    ("airline", "airline__airlines"): {"flight_number_had_the_lonest_delay_in_departure": "flight_number_had_the_longest_delay_in_departure"},
}
_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(\.0+)?(\+00:00)?$")


def _drop_suffix(v):
    if pd.isna(v):
        return v
    m = _TIMESTAMP.match(str(v).strip())
    return m.group(1) if m else v


def check_corretness_legacy(task: str, model: str, df_gt: pd.DataFrame, df: pd.DataFrame, rule: str = "typed") -> dict:
    """check_corretness with the exceptions above; both frames already sorted by the model's keys."""
    renamed = COLUMN_RENAMED.get((task, model), {})
    present = {c.lower() for c in df.columns}
    rename = {c: renamed[c.lower()].upper() if c.isupper() else renamed[c.lower()]
              for c in df.columns if c.lower() in renamed and renamed[c.lower()] not in present}
    if rename:
        df = df.rename(columns=rename)
    cols = FORMAT_ADDED.get((task, model))
    if cols:
        df_gt, df = df_gt.copy(), df.copy()
        for frame in (df_gt, df):
            for c in frame.columns:
                if c.lower() in cols:
                    frame[c] = frame[c].map(_drop_suffix)
    return check_corretness(df_gt, df, rule=rule)
