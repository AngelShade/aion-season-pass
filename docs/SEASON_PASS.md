# Aetherfall Season Pass

Ascendant Dawn is Aetherfall's character-owned 30-level season. The revised window uses a full-window illustrated celestial scene behind every page, transparent content panels, detailed metal reward frames, illustrated cyan/violet pass crests, portrait purchase frames, chapter navigation, featured finale rewards, a daily/weekly/season mission board, purchase confirmations and claim history. Open the outlined gold ticket beside the stock Shop button, **Additional Functions → Aetherfall Season Pass**, or enter `/seasonpass`. The client builder supplies a full-window native browser and close control.

| Pass | Kinah from character Inventory | Included |
| --- | ---: | --- |
| Free | 0 | Automatically active; 30 rewards; all missions |
| Premium | 1,500,000 | Free and Premium reward tracks |
| Advanced Premium | 3,000,000 | All three tracks and a one-time ten-level boost |
| Premium → Advanced | 1,500,000 | Only the price difference; same one-time boost |

The boost adds 10,000 Season XP, preserves partial progress and caps at level 30. Already earned paid rewards become claimable after upgrading. Entitlements, progress and claims are specific to this character and season; the account's ordinary premium membership is independent. Purchases are final and close at the season deadline.

## Season and missions

The first season runs **1 October–30 November 2026**, Europe/Bucharest. Claims remain open through **7 December**. Boundaries are exclusive at midnight on 1 and 8 December respectively. Each level needs 1,000 XP, for 30,000 total. Five daily missions grant 1,100 XP; six weekly missions grant 3,300; six season missions grant 10,500. Daily PvE missions alone can finish the track in 28 days; weekly/season milestones accelerate it. PvP is optional.

Credit comes from authoritative gameplay hooks: normal quest turn-ins, solo and nearby group/league NPC kill rewards, successful gathering, completed crafts excluding morphs, enemy-faction PvP kills and elapsed online minutes. Reconnecting cannot repeat the daily login reward. Remaining online across midnight also earns the next day's login credit. Killing creatures more than ten levels below the character does not count. A rival counts once per 30 minutes; same-account and same-faction kills never count, and rival levels must be within ten. One NPC death cannot grant duplicate league credit. Login/playtime progress does not accrue offline.

Daily counters reset at local midnight, weekly counters on Monday, and season counters at the season boundary. Local calendar arithmetic includes the 25-hour autumn DST day. Completed missions award XP automatically once per period, without a separate claim click. The grace period displays final mission counters and disables new progression/purchases.

## Rewards and delivery

There are 90 configured rewards, one per track per level, using existing Aion 4.8 templates and native icons. Ordinary levels give endgame progression materials and currencies. Milestones add class-matched chargeable stigmas, native event editions and plume choices. Level 30 gives the Dragon Lord's Wing Box on Free, permanent Stormwing utility pet on Premium, and a native choice of level-65 Mythic Nether Dragon King weapon or shield on Advanced. No serum or dye filler remains. Box contents, quantities, item levels and selection behavior are visible before claiming. Characters can retain items until they can use them. See [reward totals and provenance](SEASON_PASS_REWARDS.md).

Individual claim and Claim Available deliver each reward as one Black Cloud mail attachment. Claim-all requires enough room for the whole selection within the 200-letter mailbox limit. A full Inventory does not prevent delivery. The claim record, item row, mail and durable request receipt commit in one transaction. A failed operation rolls back the complete bundle. Purchases similarly commit the Kinah debit and entitlement together. Connection locking shares the native item-packet guard. After commit, mailed items/letters are marked persisted before entering the live mailbox, preventing later saves from inserting them again. Failed memory refresh disconnects the character for a fresh load; Kinah saves are quarantined if needed.

Browser mutations require an online account session and a connection-bound request form. Retrying the same form returns the saved result. Icons are supplied in memory by the installed native icon bridge; the server has no extracted item PNGs.

## Configuration and next season

`game-server/config/season-pass/season.properties` defines the season ID, server name, title, timezone, dates, XP curve, prices and boost. `missions.tsv` defines targets, cadence and XP. `rewards.tsv` defines exact items and quantities; its optional seventh field is `NONE`, `NORMAL`, `GREATER` or `MAJOR` for native class bundle resolution. Class bundles specify the Gladiator base ID and resolve to the character's advanced class at preview and claim time. Base-class claims wait for ascension. `schema.sql` creates five InnoDB tables automatically when the pass listener starts. The feature has its own authenticated HTTP listener; configure http.enabled, http.bind and http.port in season.properties. Artwork prompts are recorded in `client-mods/season-pass/ARTWORK.md`. Item icons remain native client artwork.

Keep published reward slots and economics stable under an existing season ID. To schedule a new season, wait until the prior claim grace period has finished, configure a **new unique ID**, update missions/rewards and restart GameServer. Historical progress, claims and receipts remain in SQL. This version serves one configured season at a time; it does not provide a multi-season archive window or an administrator editor. Do not replace the active configuration during its claim period. No automatic next season is currently configured.

## Server and client setup

Use the root README's Build-Server.ps1, Install-Server.ps1 and standalone client preparation commands. All required browser, signing, HUD, item-icon and server source dependencies are included.

Keep the pass listener on loopback. For players on another PC, configure the common public HTTPS origin using docs/REMOTE_SETUP.md and pass it to the client builder. No separate website account is needed; the native browser authenticates the character already online in Aion.

Configuration uses http.enabled, http.bind and http.port in season.properties. The included Central Market listener defaults to disabled and must not occupy the pass port. To use both listeners, give them different local ports and configure your reverse proxy accordingly.

Client installation creates a verified SeasonPass-backups directory. Close Aion before installing or restoring, and restore later patches first. Server distribution installation targets a new directory; keep private database settings in config/mygs.properties and retain database backups containing the five season_pass_* tables together with players, inventory and mail.

## Checks

The source includes SeasonPassCheck (rules, rewards, anonymous HTTP and isolated database transactions), SeasonPassMediaCheck (production asset bytes and allowed routes), and verify_rewards.py (native reward and class bundle data). verify_package.py verifies the complete native client package; verify_install.py exercises its installer and restore on a disposable copy.

Perform in-game acceptance on the recipient's deployment: native menu and ticket, reward icons/tooltips, daily/weekly/season progress, purchases, claim-all, Black Cloud mail, reconnect persistence and stock pets. Starting a server or hashing files alone does not establish those game interactions.
