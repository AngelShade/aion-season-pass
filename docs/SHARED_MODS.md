# Install the published Aetherfall mods together

This repository includes one combined server/client profile for Season Pass, Central Market, Wardrobe, Skip Poeta/Ishalgen Journey, and Inventory/Warehouse Expansion. Use this profile when combining these releases.

To select modules individually and add them in any order, use each repository's `Install-Module.ps1`. It retains previous selections on the same clean-source/server/client installation. See [individual module installation](INDIVIDUAL_MODULES.md). The all-five profile below remains available.

## Server operator

Build once and install into a new server folder:

```powershell
./Build-Server.ps1 -OutputRoot 'C:\Aetherfall-Mods-Build'
./Install-Server.ps1 -Archive 'C:\Aetherfall-Mods-Build\game-server\game-server.zip' -Destination 'C:\Aetherfall-Mods-Server' -SharedMods
```

The shared profile writes these settings to the new server's `config/mygs.properties`:

```properties
gameserver.sharedmods.enable = true
gameserver.inventory.unified = true
gameserver.cube.expansion_limit = 11
gameserver.warehouse.expanded = true
gameserver.poeta.journey.enable = true
gameserver.simple.secondclass.enable = false
```

Initialize and configure the emulator as described in the main README. Keep existing databases and character progress when merging into a customized server; the stock SQL seed is for a new database only. The combined source includes the gameplay hooks, prologue handlers, native reward boxes, Appearance Unlock item 168100001, and Inventory/Warehouse capacity changes.

`SharedModsHttpService` starts all four browser services after native data/database initialization. It registers `/market`, `/market/wardrobe`, `/market/pass` and `/journey` on **one** private loopback listener, using the bind and port in `config/season-pass/season.properties`. GameServer skips the standalone listeners in this profile. The existing per-character token and action-receipt checks remain active; all four native client routes use the same public origin.

For remote players, publish those routes through an HTTPS reverse proxy. Example locations inside the TLS virtual host:

```nginx
location = /market {
    proxy_pass http://127.0.0.1:8091;
    proxy_set_header Host $http_host;
    proxy_set_header Origin $http_origin;
}
location ^~ /market/ {
    proxy_pass http://127.0.0.1:8091;
    proxy_set_header Host $http_host;
    proxy_set_header Origin $http_origin;
}
location = /journey {
    proxy_pass http://127.0.0.1:8091;
    proxy_set_header Host $http_host;
    proxy_set_header Origin $http_origin;
}
location ^~ /journey/ {
    proxy_pass http://127.0.0.1:8091;
    proxy_set_header Host $http_host;
    proxy_set_header Origin $http_origin;
}
```

Do not enable a second listener on this address. The original local development server's cumulative installation has its own shared listener; preserve that integration when porting these sources into it.

## Prepare one client package

Requirements are the same as the Season Pass builder. The original client must also contain `Data/ui/game/game.pak` and its four stock loading DDS files in `Textures/loading`.

```powershell
python client-mods/shared-mods/prepare.py --client 'C:\Aion 4.8 NA' --output 'C:\Aetherfall-Mods-Staged' --server-url 'https://play.example.com'
python client-mods/shared-mods/verify.py 'C:\Aetherfall-Mods-Staged'
./client-mods/season-pass/install.ps1 -PreparedPath 'C:\Aetherfall-Mods-Staged'
```

The package includes every mod in the table below. Both Market and Season Pass get distinct HUD buttons; the menu also exposes Market, Season Pass, Wardrobe and Journey. Inventory has 180 starting slots, eleven nine-slot expansions to 279, search and detached opening; Character/Account Warehouse have 360/540 slots and search. Wardrobe's ticket is included in the client item archive, and its icon index is rebuilt for that modified archive. The stock model key and pet/Lua package contents are preserved, with all three addon archives signed together.

The builder generates four JPG files in `C:\Aetherfall-Mods-Staged-server-media`. The operator must copy those locally generated files to the new server's `config/journey/media` before starting it. They come from the recipient's own client; they are not distributed in this source repository.

## Upgrade an existing published standalone installation

Keep the current client and its recovery backups. Supply a separate supported original client copy:

```powershell
python client-mods/shared-mods/prepare.py --client 'C:\Aion-With-Mod' --original-client 'C:\Aion-Original' --output 'C:\Aetherfall-Mods-Upgrade' --server-url 'https://play.example.com'
python client-mods/shared-mods/verify.py 'C:\Aetherfall-Mods-Upgrade'
./client-mods/season-pass/install.ps1 -PreparedPath 'C:\Aetherfall-Mods-Upgrade'
```

Preparation recognizes hash-matching receipts from the published Season Pass, Market, Wardrobe, Journey and Inventory installers, and the combined profile's `Aetherfall-mods.json`. It retains all five features rather than replacing the previous feature with another standalone package. An unknown native build or an unrecorded change to a replaced archive is refused. If standalone packages were layered manually and their receipts no longer match, use their guarded restore tools in reverse installation order, or prepare a separate clean client.

Private graphics, companion or other custom native integrations are outside this published profile. Preserve those customized clients rather than installing this profile over them.

Use `Install-Module.ps1` or the combined builder for subsequent updates. The older isolated standalone installers must not be run over this cumulative profile. The client installer backs up all replaced files and the combined receipt; its printed backup path supports exact restoration to the previous installation:

```powershell
./client-mods/season-pass/restore.ps1 -BackupPath '<printed backup path>'
```

## Supported combinations and verification

| Published mod | Source | Combined integration |
| --- | --- | --- |
| Season Pass | [aion-season-pass](https://github.com/AngelShade/aion-season-pass) | Missions, Kinah tiers, native reward boxes, mail claims and ticket |
| Central Market | [aion-central-market](https://github.com/AngelShade/aion-central-market) | Market/storage service, authenticated browser and scales HUD button |
| Wardrobe | [aion-wardrobe](https://github.com/AngelShade/aion-wardrobe) | Account collection, native preview and Appearance Unlock ticket |
| Skip Poeta/Ishalgen | [aion-poeta-skip](https://github.com/AngelShade/aion-poeta-skip) | Both faction journeys, optional skip, ceremony handling and automatic login menu |
| Inventory/Warehouse | [aion-inventory](https://github.com/AngelShade/aion-inventory) | Matching server capacities, native inventory/search/warehouse/detached hooks |

`verify.py` checks the complete combined DLL bytes, collisions, all four authenticated URLs, non-overlapping HUD layouts, native slot vectors, Wardrobe item/index and three archive signatures. `SeasonPass`'s `verify_install.py` also accepts combined packages and exercises the actual PowerShell installer and exact restore on a disposable copy. `SharedModsHttpCheck` exercises all four production handlers on one isolated listener without starting GameServer.

Offline package checks do not establish recipient gameplay acceptance. Check all four menus, stock pets, Inventory/Warehouse movement/search, Wardrobe preview/apply, both faction journeys, Season Pass mission/purchase/claim/mail and relogging together in the actual game.
