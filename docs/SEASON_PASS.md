# Aetherfall Season Pass

Ascendant Dawn is Aetherfall's character-owned 30-level season. The revised window uses a full-window illustrated celestial scene behind every page, transparent content panels, detailed metal reward frames, illustrated cyan/violet pass crests, portrait purchase frames, chapter navigation, featured finale rewards, a daily/weekly/season mission board, purchase confirmations and claim history. Server ID 1 was verified as **Aetherfall** in the installed English `ui/serverlist.xml`. Open the outlined gold ticket directly above Central Market, **Additional Functions → Aetherfall Season Pass**, or enter `/seasonpass`. The window uses the existing verified full-screen native Market browser and close control; opening Central Market restores its title.

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

`game-server/config/season-pass/season.properties` defines the season ID, server name, title, timezone, dates, XP curve, prices and boost. `missions.tsv` defines targets, cadence and XP. `rewards.tsv` defines exact items and quantities; its optional seventh field is `NONE`, `NORMAL`, `GREATER` or `MAJOR` for native class bundle resolution. Class bundles specify the Gladiator base ID and resolve to the character's advanced class at preview and claim time. Base-class claims wait for ascension. `schema.sql` creates five InnoDB tables automatically when the marketplace starts. The feature requires the existing marketplace listener to be enabled. Artwork prompts are recorded in `client-mods/season-pass/ARTWORK.md`. Item icons remain native client artwork.

Keep published reward slots and economics stable under an existing season ID. To schedule a new season, wait until the prior claim grace period has finished, configure a **new unique ID**, update missions/rewards and restart GameServer. Historical progress, claims and receipts remain in SQL. This version serves one configured season at a time; it does not provide a multi-season archive window or an administrator editor. Do not replace the active configuration during its claim period. No automatic next season is currently configured.

## Remote players and the in-game browser

Pass progress, purchases and claims are stored on the GameServer for each character. The in-game window is a browser running on each player's PC, so its page URL must reach the server over the network. `127.0.0.1` works only when that player also runs GameServer on the same PC.

For remote players, keep `gameserver.marketplace.bind = 127.0.0.1` and put an HTTPS reverse proxy on the server host. Publish only `/market/pass` and `/market/pass/` through the proxy to `http://127.0.0.1:8091`; keep port 8091 private. Preserve the incoming `Host` header and forward the normal `Origin` header. The Java handler accepts an HTTP or HTTPS Origin only when its authority matches `Host`. Do not expose the session-bearing HTTP endpoint directly to the Internet.

Build each client's patch with the same public HTTPS origin, for example:

```powershell
python client-mods/season-pass/prepare.py --client "C:\Aion 4.8 NA" --output "C:\Aion-SeasonPass-Staged" --server-url "https://play.example.com"
```

Install the resulting client patch with `client-mods/season-pass/install.ps1`. The player keeps their own Aion archives and signing material; do not upload a complete game client or a prepared client snapshot. Each player installs the patch once. Their character progress and rewards remain server-side.

## Build, installation and rollback

1. Package the server from the repository root with `mvn -pl game-server -am -DskipTests "-Dassembly.skipAssembly=true" package`.
2. Stage the incremental client package with `python client-mods/season-pass/prepare.py --client "<Aion 4.8 NA>" --output "<new staging directory>"`.
3. Run the checks below. Fully close Aion normally and wait for zero online players before a graceful GameServer stop.
4. Stage a fresh server bundle with `python client-mods/season-pass/stage_server.py`. Run `client-mods/season-pass/install_server.ps1 -PreparedPath "output/season-pass/server-v9"`. The guarded installer verifies original/dependency hashes, backs up the deployed JAR and box definitions, then installs the JAR, season configuration/artwork and restored `decomposable_items.xml`. A failed installation restores its backup. A running GameServer is rejected.
5. Run `client-mods/season-pass/install.ps1 -PreparedPath "<prepared client directory>"`. Source/staged hashes and preserved files are checked before copying. A running client is rejected, and failed installation restores its backup.
6. Restart GameServer, check for `Season pass 2026-autumn ready`, and reopen Aion. Open `/seasonpass`, verify gameplay mission credit, an explicitly chosen purchase and a real claimed attachment. Also check Inventory, Central Market, Wardrobe, Additional Functions and a summoned pet.

The client patch changes the two existing browser/authentication code caves, menu registration/signatures and native ticket shortcut resources. The existing Market extension also handles the ticket click and placement; no additional executable hook is introduced. It retains all other installed executable hooks and preserves unrelated archive entries, including inventory, warehouse, speech, cursor, graphics and pet validation. Graphics/cursor backup baselines and launcher guards are composed with the new browser routes. Removing an earlier Market/Speech patch requires restoring this later Season Pass patch first; those earlier recovery receipts are left intact.

Use `client-mods/season-pass/restore.ps1 -BackupPath "<SeasonPass-backups/timestamp>"` with Aion closed to restore the exact prior client files. A later patch must be removed first. Client rollback does not revoke purchases, restore spent Kinah or delete reward/progression SQL. Keep pass data during server upgrades and include it in database backups.

## Verification

`SeasonPassCheck` verifies the curve, deadlines, DST resets, free/paid claim gates, differential upgrades and capped boosts, plus all 90 rewards against actual server templates and matching client icon metadata. With a deployment directory argument, it runs purchase/claim/mission/rival/receipt tests inside a **new empty MariaDB schema**, copies table structure only, then drops that test schema. It never changes live character data.

```powershell
javac -encoding UTF-8 -cp "game-server/target/classes;target-deploy/game-server/libs/*" -d output/season-pass/check-classes game-server/test/com/aionemu/gameserver/services/SeasonPassCheck.java
java -cp "output/season-pass/check-classes;game-server/target/classes;target-deploy/game-server/libs/*" com.aionemu.gameserver.services.SeasonPassCheck target-deploy/game-server
python client-mods/transmog-menu/tests/verify_market_browser.py --season-pass
python client-mods/transmog-menu/tests/verify_market_viewport.py
python client-mods/season-pass/verify_package.py <prepared-directory>
python client-mods/season-pass/verify_browser.py --browser-bin "<client>/bin64"
javac -encoding UTF-8 -cp "game-server/target/classes;target-deploy/game-server/libs/*" -d output/season-pass/check-classes game-server/test/com/aionemu/gameserver/services/SeasonPassMediaCheck.java
Push-Location game-server
java -cp "../output/season-pass/check-classes;target/classes;../target-deploy/game-server/libs/*" com.aionemu.gameserver.services.SeasonPassMediaCheck
Pop-Location
```

The native browser test executes real mouse clicks in Aion's Awesomium/WebKit, at 768, 1024, 1366, 1920 and 3440 pixels wide. It covers native icons, reward pages, confirmations, free claims, purchases, upgrade pricing, boosts, mission filters and claim-all/history. Screenshots go to `output/playwright/season-pass`. Its purchases and progress are isolated fixture data. It does not establish a real in-game purchase or mission acceptance.

The revised build passed 551 rules/catalog/isolated MariaDB/anonymous HTTP checks, 4,289 reward/box checks, 11 production artwork-route checks and all five native-browser viewport scenarios, including the 14-choice Mythic reward preview. The client-v4 ticket package passed hash/archive/RSA checks and a real installer/restore/tamper check on a disposable client copy. The native HUD hooks and compiled callback passed ticket/Market/Shop dispatch, unrelated-click passthrough and both HUD placements at four UI scales. Artwork checks wait for all rendered assets and verify that each purchase frame belongs to its own card. Installed bundles are `output/season-pass/client-v4` and `output/season-pass/server-v9.zip`; earlier server bundles are superseded. Server-v9 includes sixteen restored native box definitions and records original/dependency hashes, checked before installation. Restoration passed 7,792 exhaustive data checks and 13,439 native schema/JAXB/weighted-opening checks. See [box restoration evidence](RESTORED_REWARD_BOXES.md).

The server installer also passed installation, backup, changed-dependency rejection, later-file protection and injected-failure rollback checks on disposable deployment copies (`verify_server_install.ps1`). The sixteen restored box definitions are already live, and one of each was mailed to Baby with persisted attachments verified. In-game visual, hover, click, purchase and mission acceptance remain player checks; isolated checks do not establish those live interactions.

## Installed on 3 October 2026

After the user confirmed Aion was closed, client-v4 was installed with a verified backup at `SeasonPass-backups/20261003-070627-453` inside the client directory. All twenty installed files and all preserved files passed hash verification. The actual installed English localization entry is `STR_PRIVATE_SEASON_PASS_HUD` → **Aetherfall Season Pass**, referenced by the ticket in both HUD layouts. `verify_installed.py` verifies this directly from the installed archives.

Server-v9 supersedes all earlier full-build server bundles. It compiles only the three pass services and eight gameplay/HTTP hook source files against the deployed runtime, then composes those classes into the deployed JAR. Its verifier checks that changed shared methods contain pass hooks and that 3,296 unrelated JAR entries remain byte-for-byte unchanged. AFK, market, wardrobe, skill and journey classes outside that scope are preserved, including the original JAR manifest. The incremental JAR passed the 551 isolated rules/database checks and installer/backup/guard/failure-rollback checks before installation.

World and database online-player counts were both zero before native graceful shutdown. Server-v9 was installed with a backup at `target-deploy/game-server/backups/season-pass-20261003-071608-546`; GameServer was started normally as a hidden process. Logs are `target-deploy/game-server/season-pass-20261003.stdout.log` and `.stderr.log`. No live purchase, Kinah debit or automatic reward claim was performed.

Post-start verification confirmed `Season pass 2026-autumn ready: 30 levels, 17 missions, 90 rewards`, game port 7777, the private marketplace listener and connections to LoginServer/ChatServer. The live pass HTML, CSS, JavaScript and five artwork files match the deployed files exactly over HTTP. Anonymous pass state correctly returns 403. Existing Market, Wardrobe and Journey pages return 200; the Shop retains its login-required 403 response to anonymous requests. The running pass reports the configured Aetherfall name, dates and prices. All sixteen Baby test-mail attachments remained persisted with quantity one and mailbox location 127 after restart. Receipt: `output/season-pass/deploy-ready-20261003.txt`. Actual in-game hover/click/visual acceptance remains for the player after reopening Aion.

The user subsequently requested visible CMD windows for GameServer launches. Use `target-deploy/game-server/start-visible.cmd` in a normal visible CMD window for subsequent starts; its packaged source is `game-server/dist/start-visible.cmd`. When GameServer is already listening on 7777, this launcher shows the live server log and does not start another JVM or restart the server. When the port is free, it runs GameServer interactively in that CMD console, retaining the ordinary restart exit-code behavior. A visible live-log window was opened for the already-running server.
