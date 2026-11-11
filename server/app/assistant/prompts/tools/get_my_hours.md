Returns the hours the current employee worked in a date range, from the clocked time entries: the total, how many
were regular and how many were overtime, per work day. Use it for questions such as "how many hours did I work this
month?" or "how much overtime did I do?". Pass `from` and `to` as YYYY-MM-DD dates; both days are included. Never
add or subtract the numbers yourself: quote the values returned. `open_entries` counts entries that were clocked in
but not out yet; their hours are not included.
