# Aion 4.8 Aetherfall Season Pass

<img width="1316" height="774" alt="image" src="https://github.com/user-attachments/assets/8c0c62a8-b891-49f8-b6d3-79dcfa02fb96" />

Complete source release for a character-owned, 30-level Season Pass on the Beyond Aion 4.8 emulator. It includes Free, Premium and Advanced Premium tracks, daily/weekly/season missions, in-game Kinah purchases, reward previews, claim history and transactional Black Cloud mail delivery.

## Included

- Complete Commons, GameServer, LoginServer and ChatServer source and Maven build files.
- Season Pass services, authenticated HTTP listener, gameplay hooks, SQL schema, mission/reward configuration and browser artwork.
- Required native reward-box definitions and transaction-aware inventory persistence.
- A standalone client builder: native browser window, exact URL authentication hooks, item icon bridge, Additional Functions entry, `/seasonpass`, and a ticket in both English HUD layouts.
- Local archive signing with a separate Addon.key, guarded client installation and restoration, and server distribution build/install scripts.

The client integration is built from the supported original client; no previously installed Shop, Market, Wardrobe, Journey, graphics package or local recovery receipt is required. Native item artwork comes directly from the recipient's Items.pak.

## Works together with my other published mods

Install Season Pass individually with `Install-Module.ps1 -Kind source`, `-Kind server` or `-Kind client`. Run the same entry point from another module repository against the same target to add that module while preserving prior selections. See [individual installation and recovery](docs/INDIVIDUAL_MODULES.md).

| Mod | Repository | Installation with Season Pass |
| --- | --- | --- |
| Central Market | [aion-central-market](https://github.com/AngelShade/aion-central-market) | Combined profile |
| Wardrobe | [aion-wardrobe](https://github.com/AngelShade/aion-wardrobe) | Combined profile |
| Skip Poeta / Ishalgen Journey | [aion-poeta-skip](https://github.com/AngelShade/aion-poeta-skip) | Combined profile |
| Inventory and Warehouse Expansion | [aion-inventory](https://github.com/AngelShade/aion-inventory) | Combined profile |

Use the [combined installation guide](docs/SHARED_MODS.md) for these mods together. It builds one native client package and starts one shared server listener. It also supports upgrades from recorded standalone installations using a separate original client copy. Separate standalone installers should not be layered over this profile. Combined gameplay acceptance remains a recipient check.

## Requirements

Server: JDK 25, Maven and MySQL/MariaDB. Client builder: Python 3.12+, Pillow, JDK 25, and Visual Studio 2022 C++ Build Tools with the Windows SDK.

Client: original Aion 4.8 NA, 64-bit English, with its RelicCalc addon. The exact original Game.dll SHA-256 is `5334cf2164468678e45fe1a5decf58a0fbc4fd7f22cfdcbb87d28edce8d2c11c`. CrySystem and Awesomium are also checked. Use an original client copy for this builder; existing native patches are rejected rather than replaced.

## Server build and installation

```powershell
./Build-Server.ps1 -OutputRoot 'C:\Aion-SeasonPass-Build'
./Install-Server.ps1 -Archive 'C:\Aion-SeasonPass-Build\game-server\game-server.zip' -Destination 'C:\Aion-SeasonPass-Server'
```

Initialize the database using `sql/aion_gs.sql`, then configure the new server's database and LoginServer connection using the [upstream setup guide](docs/UPSTREAM_README.md). Keep private settings in ignored `config/mygs.properties`. The installer uses a new server folder and does not overwrite an existing customized deployment.

The pass starts through GameServer's normal startup and stops through its normal shutdown. `config/season-pass/season.properties` enables the pass and defaults to loopback port 8091. The included shared Central Market code is disabled by default and is not required to run its own listener. See [server and season setup](docs/SEASON_PASS.md).

## Client preparation and installation

Install Pillow with `python -m pip install Pillow`, then fully close Aion. Use the same public HTTPS origin supplied by the server operator:

```powershell
python client-mods/season-pass/prepare.py --client 'C:\Aion 4.8 NA' --output 'C:\SeasonPass-Staged' --server-url 'https://play.example.com'
python client-mods/season-pass/verify_package.py 'C:\SeasonPass-Staged'
./client-mods/season-pass/install.ps1 -PreparedPath 'C:\SeasonPass-Staged'
```

`Install-Client.cmd` provides the same steps interactively. Preparation writes only to the staging directory. Installation checks hashes and backs up every changed file. To restore, close Aion and run `client-mods/season-pass/restore.ps1 -BackupPath '<printed backup path>'`.

Open the pass using the ticket beside the stock Shop button, **Additional Functions → Aetherfall Season Pass**, or `/seasonpass`.

For client and server on the same PC, use `http://127.0.0.1:8091`. For remote players, follow [HTTPS setup](docs/REMOTE_SETUP.md). One common server address is used by all players; progress and claims remain separate for each character.

## Verification

`verify_package.py` checks native browser/authentication patch bytes, URL consistency, item indexes, both HUD layouts, English resources, the stock model key and all three addon signatures. `verify_install.py` runs the real installer and restore against a disposable client copy. The server includes rules/catalog/database and production HTTP/media checks under `game-server/test`.

Recipient acceptance includes opening the pass in Aion, native item tooltips, mission progression, Kinah purchases, mail delivery, relogging, and preserving stock pets and menus. Source and offline checks do not establish those interactions in the recipient's game.

## Credits and license

AngelShade — Aetherfall Season Pass, client integration, original ticket and celestial artwork, and shared transaction/browser foundations. Beyond Aion contributors — base emulator. roxfan — original Aion PAK codec work. GPL-3.0; see LICENSE. Aion is a trademark of its respective owner. Unofficial community modification.

No original client executable/archive, extracted item PNGs, player database, credentials, private signing key or compiled server JAR is committed. Builders use the recipient's own client and generate local binaries and signatures.
