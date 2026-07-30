# Treat each Planning Horizon as closed

V0.2 evaluates consecutive-shift runs touching the first or final day of the Planning Horizon as complete and does not evaluate transitions against assignments outside the horizon. This preserves current solver behavior and avoids adding previous-roster and next-roster boundary inputs, at the known cost of imperfect continuity between separately solved horizons. A future enhancement should introduce explicit boundary state before attempting cross-roster run and transition semantics.
