import os
import datetime
import mysql.connector
from mysql.connector import Error

# ==========================================
# Database connection
# ==========================================
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "your_password_here"),
    "database": os.environ.get("DB_NAME", "smart_medicine_reminder"),
}


def _get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        raise ConnectionError(f"Could not connect to MySQL: {e}")


def _fetch_logs(patient_id: int) -> list[dict]:
    """
    Fetch all dose logs for a patient along with schedule details.
    Returns a list of dicts with keys:
        log_id, schedule_id, medicine_name, scheduled_datetime,
        status, hour_of_day, day_of_week
    """
    query = """
        SELECT
            dl.log_id,
            dl.schedule_id,
            m.name               AS medicine_name,
            dl.scheduled_datetime,
            dl.status,
            HOUR(dl.scheduled_datetime)         AS hour_of_day,
            DAYOFWEEK(dl.scheduled_datetime)    AS day_of_week
        FROM dose_logs dl
        INNER JOIN schedules  s ON dl.schedule_id  = s.schedule_id
        INNER JOIN medicines  m ON s.medicine_id   = m.medicine_id
        WHERE s.patient_id = %s
        ORDER BY dl.scheduled_datetime DESC;
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, (patient_id,))
        return cursor.fetchall()
    except Error as e:
        raise RuntimeError(f"Query failed: {e}")
    finally:
        cursor.close()
        conn.close()


# ==========================================
# ANALYSIS FUNCTION
# ==========================================
def predict_high_risk_time(patient_id: int) -> dict:
    """
    Analyzes a patient's full dose-log history and predicts the highest-risk
    time slot (2-hour window) for missing a dose.

    Returns a dict with:
      - high_risk_window   : e.g. "06:00 – 08:00"
      - miss_rate_pct      : percentage of doses missed in that window
      - total_logs         : total recorded dose events
      - hour_breakdown     : miss rate per 2-hour block (all 12 slots)
      - medicine_breakdown : per-medicine miss rates
      - day_breakdown      : miss rate per weekday name
      - insight_message    : human-readable summary

    Miss status includes both 'Missed' and 'Skipped'.
    """
    DAY_NAMES = {
        1: "Sunday", 2: "Monday", 3: "Tuesday", 4: "Wednesday",
        5: "Thursday", 6: "Friday", 7: "Saturday",
    }

    logs = _fetch_logs(patient_id)

    if not logs:
        return {
            "high_risk_window":   "Insufficient Data",
            "miss_rate_pct":      0.0,
            "total_logs":         0,
            "hour_breakdown":     {},
            "medicine_breakdown": {},
            "day_breakdown":      {},
            "insight_message":    "No dose history found for this patient.",
        }

    total_logs = len(logs)

    # ── 1. 2-HOUR WINDOW BREAKDOWN ──────────────────────────────────────────
    # 12 slots: slot 0 → 00:00–02:00, slot 1 → 02:00–04:00, …, slot 11 → 22:00–24:00
    slots: dict[int, dict] = {i: {"total": 0, "missed": 0} for i in range(12)}

    for log in logs:
        slot_id = log["hour_of_day"] // 2
        slots[slot_id]["total"] += 1
        if log["status"] in ("Missed", "Skipped"):
            slots[slot_id]["missed"] += 1

    # Build a readable summary and find the worst slot
    hour_breakdown = {}
    worst_slot, worst_rate, worst_missed, worst_total = -1, -1.0, 0, 0

    for slot_id, counts in slots.items():
        if counts["total"] == 0:
            continue
        rate = counts["missed"] / counts["total"]
        start_h = slot_id * 2
        label = f"{start_h:02d}:00 – {start_h + 2:02d}:00"
        hour_breakdown[label] = {
            "total":    counts["total"],
            "missed":   counts["missed"],
            "miss_rate_pct": round(rate * 100, 1),
        }
        # Track worst slot (must have at least 1 miss to be "risky")
        if rate > worst_rate and counts["missed"] > 0:
            worst_rate, worst_slot = rate, slot_id
            worst_missed, worst_total = counts["missed"], counts["total"]

    if worst_slot == -1:
        high_risk_window = "No Missed Doses Detected"
        miss_rate_pct = 0.0
        insight_message = (
            "Excellent adherence! No missed or skipped doses were found in the history."
        )
    else:
        start_h = worst_slot * 2
        high_risk_window = f"{start_h:02d}:00 – {start_h + 2:02d}:00"
        miss_rate_pct = round(worst_rate * 100, 1)
        insight_message = (
            f"The patient is at highest risk between {high_risk_window}, "
            f"missing {worst_missed} of {worst_total} scheduled doses "
            f"({miss_rate_pct}%) in that window. "
            "Consider sending an extra reminder at the start of this window."
        )

    # ── 2. PER-MEDICINE BREAKDOWN ──────────────────────────────────────────
    med_stats: dict[str, dict] = {}
    for log in logs:
        name = log["medicine_name"]
        if name not in med_stats:
            med_stats[name] = {"total": 0, "missed": 0}
        med_stats[name]["total"] += 1
        if log["status"] in ("Missed", "Skipped"):
            med_stats[name]["missed"] += 1

    medicine_breakdown = {
        med: {
            "total":         s["total"],
            "missed":        s["missed"],
            "miss_rate_pct": round(s["missed"] / s["total"] * 100, 1),
        }
        for med, s in med_stats.items()
        if s["total"] > 0
    }

    # ── 3. DAY-OF-WEEK BREAKDOWN ───────────────────────────────────────────
    day_stats: dict[int, dict] = {i: {"total": 0, "missed": 0} for i in range(1, 8)}
    for log in logs:
        dow = log["day_of_week"]
        day_stats[dow]["total"] += 1
        if log["status"] in ("Missed", "Skipped"):
            day_stats[dow]["missed"] += 1

    day_breakdown = {}
    for dow, counts in day_stats.items():
        if counts["total"] == 0:
            continue
        day_breakdown[DAY_NAMES[dow]] = {
            "total":         counts["total"],
            "missed":        counts["missed"],
            "miss_rate_pct": round(counts["missed"] / counts["total"] * 100, 1),
        }

    return {
        "patient_id":         patient_id,
        "high_risk_window":   high_risk_window,
        "miss_rate_pct":      miss_rate_pct,
        "total_logs":         total_logs,
        "hour_breakdown":     hour_breakdown,
        "medicine_breakdown": medicine_breakdown,
        "day_breakdown":      day_breakdown,
        "insight_message":    insight_message,
    }


# ==========================================
# PRETTY PRINT HELPER
# ==========================================
def print_report(result: dict) -> None:
    """Prints a formatted human-readable adherence prediction report."""
    sep = "─" * 56

    print(f"\n{'═'*56}")
    print(f"  HIGH-RISK TIME PREDICTION  │  Patient ID: {result['patient_id']}")
    print(f"{'═'*56}")

    print(f"\n  {'High-Risk Window':<24} {result['high_risk_window']}")
    print(f"  {'Miss Rate in Window':<24} {result['miss_rate_pct']}%")
    print(f"  {'Total Dose Events':<24} {result['total_logs']}")
    print(f"\n  💡 {result['insight_message']}\n")

    # Hour breakdown table
    if result["hour_breakdown"]:
        print(f"  {sep}")
        print(f"  {'2-HOUR WINDOW BREAKDOWN':^56}")
        print(f"  {sep}")
        print(f"  {'Window':<18} {'Total':>7} {'Missed':>8} {'Miss Rate':>10}")
        print(f"  {sep}")
        for window, stats in sorted(result["hour_breakdown"].items()):
            bar_len = int(stats["miss_rate_pct"] / 5)  # 1 char = 5%
            bar = "█" * bar_len
            flag = "  ◄ HIGHEST RISK" if window == result["high_risk_window"] else ""
            print(
                f"  {window:<18} {stats['total']:>7} {stats['missed']:>8} "
                f"{stats['miss_rate_pct']:>8.1f}% {bar}{flag}"
            )

    # Per-medicine table
    if result["medicine_breakdown"]:
        print(f"\n  {sep}")
        print(f"  {'MISS RATE BY MEDICINE':^56}")
        print(f"  {sep}")
        print(f"  {'Medicine':<30} {'Total':>7} {'Missed':>8} {'Miss%':>6}")
        print(f"  {sep}")
        for med, s in sorted(
            result["medicine_breakdown"].items(),
            key=lambda x: -x[1]["miss_rate_pct"],
        ):
            print(f"  {med:<30} {s['total']:>7} {s['missed']:>8} {s['miss_rate_pct']:>6.1f}%")

    # Day-of-week table
    if result["day_breakdown"]:
        print(f"\n  {sep}")
        print(f"  {'MISS RATE BY DAY OF WEEK':^56}")
        print(f"  {sep}")
        print(f"  {'Day':<16} {'Total':>7} {'Missed':>8} {'Miss%':>6}")
        print(f"  {sep}")
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in day_order:
            if day in result["day_breakdown"]:
                s = result["day_breakdown"][day]
                print(f"  {day:<16} {s['total']:>7} {s['missed']:>8} {s['miss_rate_pct']:>6.1f}%")

    print(f"\n{'═'*56}\n")


# ==========================================
# STANDALONE ENTRY POINT
# ==========================================
if __name__ == "__main__":
    import sys

    patient_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Analyzing dose history for Patient ID: {patient_id} …")

    result = predict_high_risk_time(patient_id)
    print_report(result)
