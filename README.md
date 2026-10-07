# Aion 4.8 Aetherfall Season Pass client patch

This repository contains the incremental client patch tools for the Aetherfall Season Pass. Season progress, purchases and reward claims remain on the Aetherfall GameServer and are saved separately for each character. Players install the client patch once so the in-game browser can open the pass and authenticate with the character already logged in.

## Player installation

1. Confirm your server operator has enabled the Aetherfall Season Pass and has given you the server's HTTPS address.
2. Use the supported Aion 4.8 NA 64-bit English client with the Aetherfall four-window browser integration already installed (Cash Shop, Central Market, Wardrobe, and Journey). This incremental patch preserves that integration and the existing graphics, cursor, pet, and signed-addon state.
3. Install Python 3.10+, Pillow (`python -m pip install Pillow`), and Java. The client builder uses your own installed game files and signing state; it does not download or redistribute Aion files.
4. Close Aion completely. From the extracted repository, stage the patch using your own client path and the HTTPS address provided by the operator:

   ```powershell
   python client-mods/season-pass/prepare.py --client "C:\Aion 4.8 NA" --output "C:\Aion-SeasonPass-Staged" --server-url "https://play.example.com"
   ```

5. Review the staged `manifest.json`, then install it:

   ```powershell
   powershell -ExecutionPolicy Bypass -File client-mods/season-pass/install.ps1 -PreparedPath "C:\Aion-SeasonPass-Staged"
   ```

6. Start Aion, log in, and open **Additional Functions → Aetherfall Season Pass**, the ticket above Central Market, or `/seasonpass`.

The installer verifies client hashes, backs up every replaced file, and rolls back if a copy fails. To restore, close Aion and run `client-mods/season-pass/restore.ps1 -BackupPath "<printed SeasonPass-backups path>"`. Restore later client patches first.

## For the server operator

Keep the GameServer marketplace listener private on loopback and expose the Season Pass through HTTPS. The client URL is compiled into its exact native navigation and authentication allowlist, so build and distribute one matching client patch with your public HTTPS origin. See [remote player setup](docs/REMOTE_SETUP.md).

The patch builder requires the existing Aetherfall client integration and its recovery metadata. It is not a vanilla-client installer. If your players do not already have the supported Market/Shop/Wardrobe/Journey browser base, do not distribute this incremental package until that base is prepared for them.

## Package contents

- `client-mods/season-pass`: incremental builder, guarded installer/restore, custom Season Pass ticket artwork, and verification utilities.
- `client-mods/transmog-menu`, `client-mods/speech-bubbles`, `client-mods/market-shortcut`: source dependencies used to preserve the existing native browser, signed addon and HUD behavior.
- `docs/SEASON_PASS.md` and `docs/SEASON_PASS_REWARDS.md`: feature rules and reward provenance.

No Aion client archive, stock executable, private signing key, prepared client snapshot, player database, or compiled GameServer JAR is included.

## Credits and license

Based on the Beyond Aion 4.8 server emulator and its GPL-3.0 license. Original Aetherfall Season Pass artwork and integration by AngelShade. Aion is a trademark of its respective owner; this project is an unofficial community modification.
