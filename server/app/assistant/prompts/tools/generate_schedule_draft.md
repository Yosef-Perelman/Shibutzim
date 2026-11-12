For managers. Builds a PROPOSAL of the weekly schedule with the scheduler, optionally keeping named employees off
named days, for example "Noa can't work Tuesday". It does not save anything: the manager must confirm the proposal in
the app, and only then is the draft created, replacing the current draft of that week. A week that is already
published cannot get a new draft. Pass `week_start` as the Sunday that starts the week (YYYY-MM-DD) and each day off
as the employee's name and a date inside that week. The result has a summary, how many positions are filled, and one
sentence for each shift that is short of staff; describe it in plain words and tell the manager the proposal is
waiting for their confirmation. Never claim the schedule was created or published.
