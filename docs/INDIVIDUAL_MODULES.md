# Install the Aetherfall modules one at a time

Every repository has `Install-Module.ps1`. Each command selects that repository's module and retains the modules already recorded on the same source/server or client. Install client and server sides with matching selections. Any order is supported through these entry points.

| Repository | Module selected |
| --- | --- |
| aion-inventory | Inventory and Character/Account Warehouse expansion |
| aion-central-market | Central Market and its HUD button |
| aion-wardrobe | Wardrobe, native preview and Appearance Unlock ticket |
| aion-poeta-skip | Both faction journeys and login choice |
| aion-season-pass | Season Pass and its HUD ticket |

The installers use the common integration source in aion-season-pass. The other repositories download an exact pinned commit into the external workspace. They do not fetch a moving branch. All gameplay code is present in the cumulative build; only selected services, browser routes, client menus/HUD entries and capacity changes are enabled. Shared authentication/icon helpers are included where needed. This avoids overwriting an earlier feature with a standalone JAR or reusing an incompatible native hook/signing key.

## Requirements

- The clean Beyond Aion 4.8 source used by these projects: upstream commit `267ce6033f39e8d297d2ac2657e5a6e930723578`. Local edits outside changed feature files are retained; overlapping unknown edits are refused before writing.
- JDK 25, Maven, Git, Python 3.12, Pillow and Visual Studio 2022 C++ Build Tools with the Windows SDK. Client native code is compiled locally from source.
- Original English Aion 4.8 NA x64. Game.dll SHA-256: `5334cf2164468678e45fe1a5decf58a0fbc4fd7f22cfdcbb87d28edce8d2c11c`.
- A separate external workspace for source caches, builds, packages and recovery. Keep it after installation.
- GameServer and Aion must be closed during runtime/client replacements. The installer does not start either program or initialize a database.

## Apply to the same clean server source

Run this from each desired module repository, using the **same target and output paths**:

```powershell
./Install-Module.ps1 -Kind source -Target 'C:\AionSource' -OutputRoot 'D:\AionModWorkspace'
```

The first command validates and adds the common implementation to the clean source. Subsequent commands add selections in `game-server/config/mygs.properties` and retain existing selections. Unrelated source files, local configuration values and line endings survive. The source receipt is `Aetherfall-source-mods.json`.

Build that resulting source, not the isolated fork from the last downloaded repository:

```powershell
cd C:\AionSource
mvn -pl game-server -am '-Daion.build.root=D:\AionModWorkspace\source-build' package
```

The assembly excludes `config/mygs.properties`; carry the generated profile into the deployed server's `config/mygs.properties`. Merge its module settings with your database/network/operator settings. Keep your existing database and character progress. A source install is not a runtime deployment.

## Install into a new server folder

Run the client command first if selecting Journey, to obtain its server artwork. Then, from the selected module repository:

```powershell
./Install-Module.ps1 -Kind server -Target 'C:\AionServer' -OutputRoot 'D:\AionModWorkspace'
```

If the destination is absent or empty, the installer builds the full cumulative distribution and installs it. Run the command from each additional module repository with the same paths. It retains earlier selections and uses the same common build. Configure the emulator's database, login-server, network and optional chat-server as usual before your own startup. Required module tables are created by their selected production services at startup; this installer does not execute SQL or reset player data.

For Journey, supply the four JPGs printed by its client preparation:

```powershell
./Install-Module.ps1 -Kind server -Target 'C:\AionServer' -OutputRoot 'D:\AionModWorkspace' -Media '<printed client package>-server-media'
```

## Add to an existing built clean server

The first addition needs the exact original server distribution from which that folder was installed:

```powershell
./Install-Module.ps1 -Kind server -Target 'C:\AionServer' -OutputRoot 'D:\AionModWorkspace' -BaselineArchive 'D:\Downloads\stock-game-server.zip'
```

The original archive needs a `.sha256` sidecar containing its SHA-256 and filename. It must genuinely be the clean upstream distribution, not a modded server ZIP. The installer validates replacement files against this baseline; unknown changes are refused. It replaces the common libraries and affected feature data, adds required schemas/media, and merges the selected settings. Existing operator configuration, launcher scripts, unrelated files and database data are retained. Subsequent module additions use `Aetherfall-server-mods.json` and need no original archive.

`-ServerArchive` can supply an already built cumulative distribution with its checksum and `.modules.json` build receipt, avoiding another build. `Build-Server.ps1` produces both sidecars. The installer checks the integration-source fingerprint and archive hash; a distribution from another release or a standalone module JAR cannot substitute for it.

## Install clients sequentially

Run from each desired module repository, using the **same client and workspace**:

```powershell
./Install-Module.ps1 -Kind client -Target 'C:\Aion 4.8 NA' -OutputRoot 'D:\AionModWorkspace' -ServerUrl 'https://play.example.com'
```

The first install saves the original inputs externally. Each addition reads the current hash-matching `Aetherfall-mods.json`, unions the installed selection with the new module, prepares all needed shared files from those original inputs, verifies exact native hook bytes and archive signatures, and installs the verified package with an external recovery backup. Earlier menus, HUD buttons, Inventory/Warehouse layouts and Wardrobe items are rebuilt together. No separate signing keys or overlapping browser listeners are layered.

For an older recognized standalone client, provide `-OriginalClient 'C:\Aion-Original'` on the first upgrade. Unknown private native/graphics/companion modifications are refused; preserve those clients. Manually stacked legacy packages whose receipts no longer match must be restored in reverse order with their own guarded tools first.

All selected browser services use one loopback listener, configured by `config/season-pass/season.properties`. For remote players, use an HTTPS reverse proxy for `/market`, `/market/wardrobe`, `/market/pass` and `/journey`, and use the same `-ServerUrl` for every client addition. See [proxy configuration](SHARED_MODS.md).

## Recovery and updates

Keep the printed backups and original client inputs. Restore later module transactions first; a stale backup refuses to overwrite subsequent changes.

Server/source recovery:

```powershell
python '<integration source>\tools\modules\manage.py' restore --path '<printed server/source backup>'
```

Client recovery:

```powershell
& '<integration source>\client-mods\season-pass\restore.ps1' -BackupPath '<printed client backup>'
```

Updates through `Install-Module.ps1` preserve recorded selections. Keep all module checkouts on the same published integration version when updating. The older standalone installers/builders are for isolated installations; do not run them over a cumulative profile.

## Verification boundary

The offline checks cover the clean source patch, all 120 selection orders through the production planner, real source install/repeat/restore and conflict preservation, all 16 browser route combinations, all 31 native client subsets, and real sequential client file installs/restores. Server builds and isolated fixture installs are separate from gameplay acceptance.

The operator still needs to test the selected features together in the actual game: menus, stock pets, inventory/search/warehouse, Wardrobe unlock/preview/apply, both faction choices and ceremonies, Season Pass progress/purchases/claims/mail, Market transactions and relogging. Offline checks do not prove those gameplay flows.
