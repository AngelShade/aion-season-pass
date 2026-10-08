# Season Pass client integration

The standalone builder adds the complete native browser, character authentication, Additional Functions menu, /seasonpass command, ticket in both English HUD layouts, and a native item icon bridge to the supported original Aion 4.8 NA 64-bit English client.

All source dependencies are included in this repository. See the root README for requirements and build/install commands. No other custom menu or graphics package is required.

Use `prepare.py --client <original client folder> --output <new staging folder> --server-url <HTTPS origin>`, then `verify_package.py <staging folder>` before installation. Existing modified Game.dll files are rejected so cumulative custom patches are not overwritten.

`install.ps1` backs up replacements and verifies hashes; `restore.ps1` rejects later changes before restoring. The stock model Pub.key and pet/Lua archives remain unchanged. Addon.key and the three archive signatures are generated locally with an ephemeral key; no signing private key is stored.

`verify_install.py <staging folder> --output <new disposable check folder>` exercises installation, restoration and rejection of repeated/tampered packages. It never installs into the source client.
