# Frontend feature ownership

The Vite app has a single entry UI for fast hackathon iteration, with reusable pieces in `components/` and API utilities in `lib/`. These feature folders make the intended product boundaries explicit:

| Feature folder | User workflow |
| --- | --- |
| `auth/` | Sign in as Data Operator, Reviewer or Data Consumer |
| `uploads/` | Upload loan tape, servicer update or document manifest |
| `exceptions/` | Filter, inspect, comment on and decide exceptions |
| `verified-records/` | View and export human-verified loan records |
| `audit/` | Open the raw-to-verified event timeline |

The existing, working UI remains in `main.jsx` during the hackathon. New UI components should be added to the appropriate feature folder and composed into that entry point, rather than duplicating API logic.
