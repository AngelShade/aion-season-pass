# Remote player setup

GameServer owns each character's pass state. The native browser runs on the player's PC and connects to the server's common HTTPS address.

1. Configure `config/season-pass/season.properties` on the server:

   ```properties
   http.enabled=true
   http.bind=127.0.0.1
   http.port=8091
   ```

2. Keep other listeners off on that port. The included Central Market listener defaults to disabled. If another local service uses 8091, select a free port for this listener and update the reverse proxy.
3. Configure a public hostname and valid TLS certificate. Publish the pass through a reverse proxy to the private loopback listener. Example Nginx locations inside your TLS virtual host:

   ```nginx
   location = /market/pass {
       proxy_pass http://127.0.0.1:8091;
       proxy_set_header Host $http_host;
       proxy_set_header Origin $http_origin;
   }
   location ^~ /market/pass/ {
       proxy_pass http://127.0.0.1:8091;
       proxy_set_header Host $http_host;
       proxy_set_header Origin $http_origin;
   }
   ```

4. Build each supported original client with `--server-url https://your.actual.hostname`. The exact origin is embedded in the browser authentication allowlist, Lua menu and native icon bridge. Explicit default ports are normalized; non-default ports must agree with your proxy and public URL.
5. Install the prepared package, log into the game and open `/seasonpass`. The native game security token authenticates the current online character; players do not enter a separate website password.

Only loopback may use plain HTTP. A loopback address reaches the player's own PC, so remote players must use the public HTTPS origin. Keep port 8091 private and permit inbound HTTPS to the proxy. An anonymous state/action request returns 403 as expected.

Item icon URLs are fulfilled inside the native client from its unchanged Items.pak. No extracted icon PNGs or client archives need to be hosted. Share this source release; each recipient prepares a patch using their own original client files.
