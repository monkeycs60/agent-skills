# The user's real Chrome

In the default mode, `ab` attaches to the Chrome the user already has open (agent-browser's `--auto-connect`) and works in a tab reserved for the conversation (`--pin-tab`). The agent inherits every login of that profile: no credentials to type, no cookies to export.

## Setup, once per machine

1. Chrome 144 or later, open with the profile whose logins are needed.
2. The user opens `chrome://inspect/#remote-debugging` and allows remote debugging. Chrome then writes its debugging port into its profile folder, where `ab` finds it on its own.
3. On a conversation's first command, Chrome shows a prompt to allow the connection. The user accepts it, then the agent retries the command.

Don't work around this prompt or take over someone else's profile. If Chrome is missing, the user installs it from https://www.google.com/chrome/.

## When Chrome asks for permission again

Each conversation opens its own connection, so Chrome may ask again:

- on the first command of each new conversation;
- after Chrome restarts;
- after an hour without commands in the conversation, once agent-browser has closed its connection.

After a Chrome restart, the next command reconnects by itself, with no action from the agent once permission is granted.

## What the user sees

- The agent's tab opens in the active Chrome window and comes to the front there. Each new conversation opens one more.
- `ab close` closes that tab and only that one. `ab` never closes Chrome or the user's tabs.
- Keyboard focus and the active window are not protected: depending on the system, opening the tab or an agent click can bring Chrome to the front. Warn the user before a long flow in real Chrome, or switch to isolated mode if their logins aren't needed.

## Slow clicks: the agent's tab is in the background

Chrome doesn't paint a hidden tab. As soon as another tab comes in front of the agent's tab in the same window (the user switches tabs, another conversation opens its own), every agent click waits about 5 s, versus a few tens of milliseconds in the foreground. `fill`, `press`, `snapshot`, `read` and `screenshot` stay fast.

Fixes, from simplest to safest:

- only one conversation at a time in real Chrome;
- the user drags the agent's tab into its own window: the active tab of each visible window keeps being painted;
- isolated mode for anything that doesn't need their logins;
- for a video, keep the agent's tab in the foreground for the whole take.

## Advanced option: a Chrome dedicated to agents (`AB_CDP`)

A second Chrome, with its own profile, avoids the permission prompts and leaves the main Chrome untouched. The user signs in to the useful sites once; the logins stay there.

```bash
google-chrome --user-data-dir="$HOME/.chrome-agents" --remote-debugging-port=9222
open -na "Google Chrome" --args --user-data-dir="$HOME/.chrome-agents" --remote-debugging-port=9222
AB_CDP=9222 ab open https://example.com
```

The first line is for Linux, the second for macOS. Chrome ignores `--remote-debugging-port` on the default profile: the `--user-data-dir` folder must be a separate one. While that port is open, any local program can drive this profile and read its cookies: keep this Chrome for accounts the user accepts to expose there. `AB_CDP` also accepts a `ws://…` URL to a CDP relay of their choice.

## Failures

| Symptom | Cause | Action |
|---|---|---|
| `No running Chrome instance found`, followed by `ab`'s hint | Chrome closed, or remote debugging not allowed | Ask the user to open Chrome and check `chrome://inspect/#remote-debugging`. If their logins aren't needed: `AB_ISOLATED=1`. |
| The first command fails or hangs | Permission prompt shown in Chrome | Tell the user, wait for their click, retry. |
| `tab_gone` | The agent's tab was closed | `ab` opens a blank one on the next command: run `open` again. If the error persists: `ab tab new about:blank`. |
| Every click takes about 5 s | Agent's tab in the background | See "Slow clicks" above. |
| `Unknown ref` | Refs expired after navigation | `ab snapshot -i`, then use the new refs. |
| Any other unexpected error | Install or daemon in a bad state | `AB_ISOLATED=1 ab doctor`. |
