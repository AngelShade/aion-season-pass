# Remote player network setup

The Season Pass is server-managed. Its HTML and API are rendered by each player's in-game browser, which runs on that player's own PC. Therefore a loopback URL such as `127.0.0.1` reaches the player's PC, not the GameServer. For remote players, use a public DNS name with a valid TLS certificate.

## Keep the application listener private

In `config/main/gameserver.properties`, retain:

```properties
gameserver.marketplace.enable = true
gameserver.marketplace.bind = 127.0.0.1
gameserver.marketplace.port = 8091
```

Do not expose port 8091 directly to the Internet. Put a TLS reverse proxy on the GameServer host and publish only `/market/pass` and `/market/pass/` to the local listener. Preserve the incoming `Host` and `Origin` headers. Example Nginx locations inside the TLS virtual host:

```nginx
location = /market/pass {
    proxy_pass http://127.0.0.1:8091;
    proxy_set_header Host $host;
    proxy_set_header Origin $http_origin;
}

location ^~ /market/pass/ {
    proxy_pass http://127.0.0.1:8091;
    proxy_set_header Host $host;
    proxy_set_header Origin $http_origin;
}
```

Configure a valid certificate for the same DNS name and allow inbound HTTPS (normally port 443) in the host firewall. Keep HTTP redirected to HTTPS at the proxy. Do not set a public marketplace bind address or forward port 8091 from the router.

## Build the matching player patch

From the operator's supported client build, prepare the incremental patch with the public HTTPS origin:

```powershell
python client-mods/season-pass/prepare.py --client "C:\Aion 4.8 NA" --output "C:\Aion-SeasonPass-Staged" --server-url "https://play.example.com"
```

Replace the example with the operator's actual origin. The builder rejects remote plain HTTP. The generated native hook only recognizes the exact pass URL and preserves the existing local routes for the other installed windows. Give players the same origin so their in-game browser reaches the server. Do not upload the prepared directory: it contains client files copied from one installation. Share this source repository and let each player stage the patch locally.

Each player must already have the supported Aetherfall client browser integration. This package does not install the server feature, configure DNS/TLS, or provide a generic vanilla-client conversion.
